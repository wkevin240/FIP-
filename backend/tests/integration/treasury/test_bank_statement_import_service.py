from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.accounting.bank_transaction import BankTransaction
from app.models.audit.audit_event import AuditEvent
from app.models.treasury.bank_statement_import import BankStatementImport
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.treasury.bank_statement_import_service import (
    BankStatementImportService,
)
from app.services.treasury.transaction_service import TreasuryTransactionService
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.treasury.test_treasury_accounting_service import _context

HEADER = "external_id,transaction_date,value_date,amount,description,reference\n"


def _csv(*rows: str) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


@pytest.mark.asyncio
async def test_csv_import_creates_canonical_transactions_deduplicates_and_audits(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    existing_external_id = f"EXISTING-{uuid4().hex[:12]}"
    existing = await TreasuryTransactionService(db_session).create_transaction(
        organization_id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile_id,
            transaction_date="2026-02-01",
            amount=Decimal("12.00"),
            description="Existing transaction",
            external_id=existing_external_id,
        ),
    )
    content = _csv(
        "IMPORTED-001,2026-02-02,2026-02-03,125.50,Customer collection,INV-001",
        f"{existing_external_id},2026-02-01,,12.00,Existing transaction,",
        "IMPORTED-002,2026-02-04,, -25.50 ,Bank charge,FEE-001",
    )
    service = BankStatementImportService(db_session)
    first = await service.import_csv(
        organization_id,
        "import-tester",
        bank_profile_id,
        "csv-import-001",
        "february.csv",
        content,
    )
    repeated = await service.import_csv(
        organization_id,
        "import-tester",
        bank_profile_id,
        "csv-import-001",
        "february.csv",
        content,
    )

    assert first.id == repeated.id
    assert first.row_count == 3
    assert first.imported_count == 2
    assert first.duplicate_count == 1
    assert [line.status for line in first.lines] == [
        "IMPORTED",
        "DUPLICATE",
        "IMPORTED",
    ]
    assert first.lines[1].bank_transaction_id == existing.id
    imported_amounts = list(
        await db_session.scalars(
            select(BankTransaction.amount)
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.external_id.in_(["IMPORTED-001", "IMPORTED-002"]),
            )
            .order_by(BankTransaction.external_id)
        )
    )
    assert imported_amounts == [Decimal("125.50"), Decimal("-25.50")]
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_STATEMENT_IMPORTED",
                AuditEvent.resource_id == first.id,
            )
        )
        == 1
    )
    with pytest.raises(
        HTTPException, match="Idempotency key was already used with a different import"
    ) as conflicting_reuse:
        await service.import_csv(
            organization_id,
            "import-tester",
            bank_profile_id,
            "csv-import-001",
            "february.csv",
            _csv("IMPORTED-DIFFERENT,2026-02-02,,125.50,Customer collection,INV-001"),
        )
    assert conflicting_reuse.value.status_code == 409


@pytest.mark.asyncio
async def test_csv_import_rejects_malformed_content_and_rolls_back(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    service = BankStatementImportService(db_session)
    malformed = _csv(
        "DUP-001,2026-02-02,,10.00,Customer collection,INV-001",
        "DUP-001,2026-02-03,,11.00,Duplicate external ID,INV-002",
    )
    with pytest.raises(HTTPException, match="duplicate external_id") as invalid:
        await service.import_csv(
            organization_id,
            "import-tester",
            bank_profile_id,
            "csv-import-invalid",
            "invalid.csv",
            malformed,
        )
    assert invalid.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(BankStatementImport.id)).where(
                BankStatementImport.organization_id == organization_id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_STATEMENT_IMPORTED",
            )
        )
        == 0
    )

    other_organization, _, other_bank_profile, _, _, _ = await _context(db_session)
    other_organization_id = other_organization.id
    with pytest.raises(
        HTTPException, match="Treasury bank account not found"
    ) as cross_tenant:
        await service.import_csv(
            organization_id,
            "import-tester",
            other_bank_profile.id,
            "csv-import-tenant",
            "tenant.csv",
            _csv("TENANT-001,2026-02-02,,10.00,Tenant guard,"),
        )
    assert cross_tenant.value.status_code == 404
    assert other_organization_id != organization_id
