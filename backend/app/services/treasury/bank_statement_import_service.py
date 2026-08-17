import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from typing import Any

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
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BankStatementImportService:
    """Imports normalized CSV and OFX v2 XML statements into canonical transactions."""

    _CSV_HEADERS = (
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
        try:
            rows = self._parse_csv_rows(content)
        except ValueError as exc:
            raise self._validation_error(exc) from exc
        return await self._import_rows(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            treasury_bank_account_id=treasury_bank_account_id,
            idempotency_key=idempotency_key,
            source_filename=source_filename,
            content=content,
            format_version="CSV_V1",
            rows=rows,
            source_account_number=None,
        )

    async def import_ofx(
        self,
        organization_id: str,
        actor_user_id: str,
        treasury_bank_account_id: str,
        idempotency_key: str,
        source_filename: str,
        content: bytes,
    ) -> BankStatementImport:
        try:
            source_account_number, rows = self._parse_ofx_rows(content)
        except ValueError as exc:
            raise self._validation_error(exc) from exc
        return await self._import_rows(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            treasury_bank_account_id=treasury_bank_account_id,
            idempotency_key=idempotency_key,
            source_filename=source_filename,
            content=content,
            format_version="OFX_V2_XML",
            rows=rows,
            source_account_number=source_account_number,
        )

    async def _import_rows(
        self,
        *,
        organization_id: str,
        actor_user_id: str,
        treasury_bank_account_id: str,
        idempotency_key: str,
        source_filename: str,
        content: bytes,
        format_version: str,
        rows: list[dict[str, Any]],
        source_account_number: str | None,
    ) -> BankStatementImport:
        content_hash = sha256(content).hexdigest()
        existing = await self.imports.get_import_by_key(
            organization_id, idempotency_key
        )
        if existing is not None:
            self._ensure_same_request(
                existing,
                treasury_bank_account_id,
                content_hash,
                source_filename,
                format_version,
            )
            return existing
        try:
            bank_account = await self._get_active_bank_account(
                organization_id, treasury_bank_account_id
            )
            if source_account_number is not None and not self._same_account_identifier(
                source_account_number, bank_account.account_number
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="OFX account identifier does not match the treasury bank account",
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
                    existing,
                    treasury_bank_account_id,
                    content_hash,
                    source_filename,
                    format_version,
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
                format_version=format_version,
                row_count=len(rows),
                imported_count=imported_count,
                duplicate_count=duplicate_count,
                status="COMPLETED",
            )
            await self.imports.create_import(statement_import)

            import_lines: list[BankStatementImportLine] = []
            for row in rows:
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
                        line_number=row["line_number"],
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
                    "format_version": format_version,
                },
                transaction_id=statement_import.id,
                request_id=idempotency_key,
            )
            await self.session.commit()
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
                    existing,
                    treasury_bank_account_id,
                    content_hash,
                    source_filename,
                    format_version,
                )
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank statement import changed concurrently",
            ) from exc
        return await self._reload_import(organization_id, statement_import.id)

    def _parse_csv_rows(self, content: bytes) -> list[dict[str, Any]]:
        text_content = self._decode_content(content)
        reader = csv.DictReader(StringIO(text_content, newline=""))
        if reader.fieldnames is None or tuple(reader.fieldnames) != self._CSV_HEADERS:
            raise ValueError(
                "CSV header must be exactly external_id,transaction_date,value_date,amount,description,reference"
            )
        rows: list[dict[str, Any]] = []
        for line_number, raw in enumerate(reader, start=2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"CSV line {line_number} has an invalid column count")
            rows.append(
                self._normalized_row(
                    line_number=line_number,
                    external_id=raw["external_id"],
                    transaction_date_text=raw["transaction_date"],
                    value_date_text=raw["value_date"],
                    amount_text=raw["amount"],
                    description=raw["description"],
                    reference=raw["reference"],
                    source_label=f"CSV line {line_number}",
                )
            )
        return self._validate_row_collection(rows, "Bank statement file")

    def _parse_ofx_rows(self, content: bytes) -> tuple[str, list[dict[str, Any]]]:
        text_content = self._decode_content(content)
        if not text_content.lstrip().startswith("<?xml"):
            raise ValueError("OFX import supports OFX v2 XML files only")
        try:
            root = ElementTree.fromstring(text_content)
        except (DefusedXmlException, ElementTree.ParseError) as exc:
            raise ValueError("OFX file is not valid safe XML") from exc
        if self._tag_name(root.tag) != "OFX":
            raise ValueError("OFX XML root element must be OFX")
        for status_element in self._elements_named(root, "STATUS"):
            code = self._child_text(status_element, "CODE")
            if code is not None and code.strip() != "0":
                raise ValueError(
                    f"OFX response status {code.strip()} is not successful"
                )
        account_ids = {
            account_id
            for account in self._elements_named(root, "BANKACCTFROM")
            if (account_id := self._child_text(account, "ACCTID"))
        }
        if len(account_ids) != 1:
            raise ValueError("OFX file must contain exactly one BANKACCTFROM ACCTID")
        rows: list[dict[str, Any]] = []
        for index, transaction in enumerate(
            self._elements_named(root, "STMTTRN"), start=1
        ):
            description = (
                self._child_text(transaction, "NAME")
                or self._nested_text(transaction, "PAYEE", "NAME")
                or self._child_text(transaction, "MEMO")
            )
            fitid = self._child_text(transaction, "FITID")
            posted_date = self._child_text(transaction, "DTPOSTED")
            amount = self._child_text(transaction, "TRNAMT")
            if not all((description, fitid, posted_date, amount)):
                raise ValueError(
                    f"OFX transaction {index} requires FITID, DTPOSTED, TRNAMT and NAME or MEMO"
                )
            reference = self._child_text(transaction, "CHECKNUM") or self._child_text(
                transaction, "REFNUM"
            )
            rows.append(
                self._normalized_row(
                    line_number=index,
                    external_id=fitid,
                    transaction_date_text=self._ofx_date(posted_date),
                    value_date_text="",
                    amount_text=amount,
                    description=description,
                    reference=reference or "",
                    source_label=f"OFX transaction {index}",
                )
            )
        return next(iter(account_ids)), self._validate_row_collection(rows, "OFX file")

    def _normalized_row(
        self,
        *,
        line_number: int,
        external_id: str,
        transaction_date_text: str,
        value_date_text: str,
        amount_text: str,
        description: str,
        reference: str,
        source_label: str,
    ) -> dict[str, Any]:
        external_id = external_id.strip()
        description = description.strip()
        reference = reference.strip() or None
        value_date_text = value_date_text.strip()
        if not external_id or not description:
            raise ValueError(f"{source_label} requires external_id and description")
        try:
            transaction_date = date.fromisoformat(transaction_date_text.strip())
            value_date = (
                date.fromisoformat(value_date_text) if value_date_text else None
            )
            amount = Decimal(amount_text.strip())
        except (ArithmeticError, ValueError) as exc:
            raise ValueError(
                f"{source_label} contains an invalid date or amount"
            ) from exc
        if amount == 0 or amount.as_tuple().exponent < -2:
            raise ValueError(
                f"{source_label} amount must be non-zero with at most 2 decimals"
            )
        if len(external_id) > 100 or len(description) > 500:
            raise ValueError(f"{source_label} exceeds field length limits")
        if reference is not None and len(reference) > 100:
            raise ValueError(f"{source_label} reference exceeds 100 characters")
        normalized_amount = amount.quantize(Decimal("0.01"))
        canonical = "|".join(
            (
                external_id,
                transaction_date.isoformat(),
                value_date.isoformat() if value_date else "",
                format(normalized_amount, ".2f"),
                description,
                reference or "",
            )
        )
        return {
            "line_number": line_number,
            "external_id": external_id,
            "transaction_date": transaction_date,
            "value_date": value_date,
            "amount": normalized_amount,
            "description": description,
            "reference": reference,
            "row_hash": sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def _validate_row_collection(
        self, rows: list[dict[str, Any]], source_label: str
    ) -> list[dict[str, Any]]:
        if not rows:
            raise ValueError(f"{source_label} must contain at least one transaction")
        if len(rows) > self._MAX_ROWS:
            raise ValueError(f"{source_label} exceeds the {self._MAX_ROWS} row limit")
        external_ids = [row["external_id"] for row in rows]
        if len(external_ids) != len(set(external_ids)):
            raise ValueError(f"{source_label} contains duplicate external_id")
        return rows

    def _decode_content(self, content: bytes) -> str:
        if not content:
            raise ValueError("Bank statement file must not be empty")
        if len(content) > self._MAX_CONTENT_BYTES:
            raise ValueError("Bank statement file exceeds the 5 MiB limit")
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Bank statement file must be UTF-8 encoded") from exc

    @staticmethod
    def _ofx_date(value: str) -> str:
        value = value.strip()
        if len(value) < 8 or not value[:8].isdigit():
            raise ValueError("OFX DTPOSTED must start with YYYYMMDD")
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()
        except ValueError as exc:
            raise ValueError("OFX DTPOSTED contains an invalid date") from exc

    @staticmethod
    def _tag_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].upper()

    @classmethod
    def _elements_named(cls, element: Any, name: str) -> list[Any]:
        return [child for child in element.iter() if cls._tag_name(child.tag) == name]

    @classmethod
    def _child_text(cls, element: Any, name: str) -> str | None:
        for child in element:
            if cls._tag_name(child.tag) == name and child.text:
                return child.text.strip()
        return None

    @classmethod
    def _nested_text(
        cls, element: Any, parent_name: str, child_name: str
    ) -> str | None:
        for child in element:
            if cls._tag_name(child.tag) == parent_name:
                return cls._child_text(child, child_name)
        return None

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
    def _same_account_identifier(left: str, right: str) -> bool:
        return left.strip().replace(" ", "") == right.strip().replace(" ", "")

    @staticmethod
    def _validation_error(error: ValueError) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )

    @staticmethod
    def _ensure_same_request(
        statement_import: BankStatementImport,
        treasury_bank_account_id: str,
        content_hash: str,
        source_filename: str,
        format_version: str,
    ) -> None:
        if (
            statement_import.treasury_bank_account_id != treasury_bank_account_id
            or statement_import.content_hash != content_hash
            or statement_import.source_filename != source_filename
            or statement_import.format_version != format_version
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different import",
            )
