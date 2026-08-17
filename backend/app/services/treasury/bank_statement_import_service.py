import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import StringIO

from app.models.accounting.bank_transaction import BankTransaction
from app.models.treasury.bank_statement_import import (
    BankStatementImport,
    BankStatementImportLine,
)
from app.repositories.treasury.bank_account_repository import (
    TreasuryBankAccountRepository,
)
from app.repositories.treasury.bank_statement_import_repository import (
    BankStatementImportRepository,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BankStatementImportService:
    """Imports a strict, normalized CSV statement into canonical bank transactions."""

    _HEADERS = (
        "external_id",
        "transaction_date",
        "value_date",
        "amount",
        "description",
        "reference",
    )
    _MAX_CONTENT_BYTES = 5 * 1024 * 1024
    _MAX_ROWS = 10_000

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bank_accounts = TreasuryBankAccountRepository(session)
        self.imports = BankStatementImportRepository(session)
        self.audit = AuditService(session)

    async def import_csv(
        self,
        organization_id: str,
        actor_user_id: str,
        treasury_bank_account_id: str,
        idempotency_key: str,
        source_filename: str,
        content: bytes,
    ) -> BankStatementImport:
        content_hash = sha256(content).hexdigest()
        existing = await self.imports.get_import_by_key(
            organization_id, idempotency_key
        )
        if existing is not None:
            self._ensure_same_request(
                existing, treasury_bank_account_id, content_hash, source_filename
            )
            return existing
        try:
            rows = self._parse_rows(content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        try:
            bank_account = await self._get_active_bank_account(
                organization_id, treasury_bank_account_id
            )
            await self.imports.lock_resources(
                {
                    f"key:{idempotency_key}",
                    *{
                        f"external:{bank_account.ledger_account_id}:{row['external_id']}"
                        for row in rows
                    },
                }
            )
            existing = await self.imports.get_import_by_key(
                organization_id, idempotency_key
            )
            if existing is not None:
                self._ensure_same_request(
                    existing, treasury_bank_account_id, content_hash, source_filename
                )
                return existing

            existing_transactions = await self.imports.get_transactions_by_external_ids(
                organization_id,
                bank_account.ledger_account_id,
                {row["external_id"] for row in rows},
            )
            duplicate_count = sum(
                row["external_id"] in existing_transactions for row in rows
            )
            imported_count = len(rows) - duplicate_count
            statement_import = BankStatementImport(
                organization_id=organization_id,
                treasury_bank_account_id=treasury_bank_account_id,
                imported_by_user_id=actor_user_id,
                idempotency_key=idempotency_key,
                content_hash=content_hash,
                source_filename=source_filename,
                format_version="CSV_V1",
                row_count=len(rows),
                imported_count=imported_count,
                duplicate_count=duplicate_count,
                status="COMPLETED",
            )
            await self.imports.create_import(statement_import)

            import_lines: list[BankStatementImportLine] = []
            for line_number, row in enumerate(rows, start=2):
                existing_transaction = existing_transactions.get(row["external_id"])
                if existing_transaction is None:
                    transaction = BankTransaction(
                        organization_id=organization_id,
                        bank_account_id=bank_account.ledger_account_id,
                        transaction_date=row["transaction_date"],
                        value_date=row["value_date"],
                        amount=row["amount"],
                        description=row["description"],
                        reference=row["reference"],
                        external_id=row["external_id"],
                    )
                    await self.imports.create_transaction(transaction)
                    existing_transactions[row["external_id"]] = transaction
                    line_status = "IMPORTED"
                else:
                    transaction = existing_transaction
                    line_status = "DUPLICATE"
                import_lines.append(
                    BankStatementImportLine(
                        organization_id=organization_id,
                        statement_import_id=statement_import.id,
                        line_number=line_number,
                        external_id=row["external_id"],
                        bank_transaction_id=transaction.id,
                        row_hash=row["row_hash"],
                        status=line_status,
                    )
                )
            await self.imports.create_lines(import_lines)
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="BANK_STATEMENT_IMPORTED",
                resource_type="BankStatementImport",
                resource_id=statement_import.id,
                new_value={
                    "treasury_bank_account_id": treasury_bank_account_id,
                    "content_hash": content_hash,
                    "row_count": len(rows),
                    "imported_count": imported_count,
                    "duplicate_count": duplicate_count,
                    "format_version": "CSV_V1",
                },
                transaction_id=statement_import.id,
                request_id=idempotency_key,
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.imports.get_import_by_key(
                organization_id, idempotency_key
            )
            if existing is not None:
                self._ensure_same_request(
                    existing, treasury_bank_account_id, content_hash, source_filename
                )
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank statement import changed concurrently",
            ) from exc
        return await self._reload_import(organization_id, statement_import.id)

    def _parse_rows(self, content: bytes) -> list[dict[str, object]]:
        if not content:
            raise ValueError("Bank statement file must not be empty")
        if len(content) > self._MAX_CONTENT_BYTES:
            raise ValueError("Bank statement file exceeds the 5 MiB limit")
        try:
            text_content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Bank statement file must be UTF-8 encoded") from exc
        reader = csv.DictReader(StringIO(text_content, newline=""))
        if reader.fieldnames is None or tuple(reader.fieldnames) != self._HEADERS:
            raise ValueError(
                "CSV header must be exactly external_id,transaction_date,value_date,amount,description,reference"
            )
        rows: list[dict[str, object]] = []
        external_ids: set[str] = set()
        for line_number, raw in enumerate(reader, start=2):
            if len(rows) >= self._MAX_ROWS:
                raise ValueError("Bank statement exceeds the 10000 row limit")
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"CSV line {line_number} has an invalid column count")
            external_id = raw["external_id"].strip()
            description = raw["description"].strip()
            reference = raw["reference"].strip() or None
            value_date_text = raw["value_date"].strip()
            if not external_id or not description:
                raise ValueError(
                    f"CSV line {line_number} requires external_id and description"
                )
            if external_id in external_ids:
                raise ValueError(f"CSV contains duplicate external_id {external_id}")
            external_ids.add(external_id)
            try:
                transaction_date = date.fromisoformat(raw["transaction_date"].strip())
                value_date = (
                    date.fromisoformat(value_date_text) if value_date_text else None
                )
                amount = Decimal(raw["amount"].strip())
            except (ArithmeticError, ValueError) as exc:
                raise ValueError(
                    f"CSV line {line_number} contains an invalid date or amount"
                ) from exc
            if amount == 0 or amount.as_tuple().exponent < -2:
                raise ValueError(
                    f"CSV line {line_number} amount must be non-zero with at most 2 decimals"
                )
            if len(external_id) > 100 or len(description) > 500:
                raise ValueError(f"CSV line {line_number} exceeds field length limits")
            if reference is not None and len(reference) > 100:
                raise ValueError(
                    f"CSV line {line_number} reference exceeds 100 characters"
                )
            canonical = "|".join(
                (
                    external_id,
                    transaction_date.isoformat(),
                    value_date.isoformat() if value_date else "",
                    format(amount, ".2f"),
                    description,
                    reference or "",
                )
            )
            rows.append(
                {
                    "external_id": external_id,
                    "transaction_date": transaction_date,
                    "value_date": value_date,
                    "amount": amount.quantize(Decimal("0.01")),
                    "description": description,
                    "reference": reference,
                    "row_hash": sha256(canonical.encode("utf-8")).hexdigest(),
                }
            )
        if not rows:
            raise ValueError("Bank statement file must contain at least one row")
        return rows

    async def _get_active_bank_account(
        self, organization_id: str, treasury_bank_account_id: str
    ):
        bank_account = await self.bank_accounts.get_by_id(
            organization_id, treasury_bank_account_id
        )
        if bank_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Treasury bank account not found",
            )
        if not bank_account.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Treasury bank account is inactive",
            )
        return bank_account

    async def _reload_import(
        self, organization_id: str, statement_import_id: str
    ) -> BankStatementImport:
        result = await self.imports.get_import(organization_id, statement_import_id)
        if result is None:
            raise RuntimeError("Bank statement import could not be reloaded")
        return result

    @staticmethod
    def _ensure_same_request(
        statement_import: BankStatementImport,
        treasury_bank_account_id: str,
        content_hash: str,
        source_filename: str,
    ) -> None:
        if (
            statement_import.treasury_bank_account_id != treasury_bank_account_id
            or statement_import.content_hash != content_hash
            or statement_import.source_filename != source_filename
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different import",
            )
