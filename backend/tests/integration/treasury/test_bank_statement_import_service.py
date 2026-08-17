from datetime import date
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


OFX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<OFX>
  <SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE></STATUS></SONRS></SIGNONMSGSRSV1>
  <BANKMSGSRSV1><STMTTRNRS><STATUS><CODE>0</CODE></STATUS><STMTRS>
    <CURDEF>XOF</CURDEF>
    <BANKACCTFROM><BANKID>FIP</BANKID><ACCTID>{account_number}</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
    <BANKTRANLIST>{transactions}</BANKTRANLIST>
  </STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


def _ofx_transaction(fitid: str, posted: str, amount: str, name: str) -> str:
    return (
        "<STMTTRN>"
        f"<TRNTYPE>OTHER</TRNTYPE><DTPOSTED>{posted}</DTPOSTED>"
        f"<TRNAMT>{amount}</TRNAMT><FITID>{fitid}</FITID>"
        f"<NAME>{name}</NAME><MEMO>Memo {fitid}</MEMO>"
        "</STMTTRN>"
    )


@pytest.mark.asyncio
async def test_ofx_v2_import_normalizes_transactions_idempotently_and_audits(
    db_session: AsyncSession,
) -> None:
    from app.models.treasury.bank_account import TreasuryBankAccount

    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    bank_account = await db_session.get(TreasuryBankAccount, bank_profile_id)
    assert bank_account is not None
    account_number = bank_account.account_number
    content = OFX_TEMPLATE.format(
        account_number=account_number,
        transactions=(
            _ofx_transaction("OFX-FITID-001", "20260211123000", "210.50", "Collection")
            + _ofx_transaction("OFX-FITID-002", "20260212090000", "-10.50", "Bank fee")
        ),
    ).encode("utf-8")
    service = BankStatementImportService(db_session)
    first = await service.import_ofx(
        organization_id,
        "import-tester",
        bank_profile_id,
        "ofx-import-001",
        "february.ofx",
        content,
    )
    repeated = await service.import_ofx(
        organization_id,
        "import-tester",
        bank_profile_id,
        "ofx-import-001",
        "february.ofx",
        content,
    )

    assert first.id == repeated.id
    assert first.format_version == "OFX_V2_XML"
    assert first.imported_count == 2
    assert first.duplicate_count == 0
    amounts = list(
        await db_session.scalars(
            select(BankTransaction.amount)
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.external_id.in_(["OFX-FITID-001", "OFX-FITID-002"]),
            )
            .order_by(BankTransaction.external_id)
        )
    )
    assert amounts == [Decimal("210.50"), Decimal("-10.50")]
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


@pytest.mark.asyncio
async def test_ofx_v2_import_rejects_account_mismatch_duplicate_fitid_and_unsafe_xml(
    db_session: AsyncSession,
) -> None:
    from app.models.treasury.bank_account import TreasuryBankAccount

    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    bank_account = await db_session.get(TreasuryBankAccount, bank_profile_id)
    assert bank_account is not None
    account_number = bank_account.account_number
    service = BankStatementImportService(db_session)

    with pytest.raises(HTTPException, match="account identifier") as account_mismatch:
        await service.import_ofx(
            organization_id,
            "import-tester",
            bank_profile_id,
            "ofx-import-account-mismatch",
            "mismatch.ofx",
            OFX_TEMPLATE.format(
                account_number="OTHER-ACCOUNT",
                transactions=_ofx_transaction(
                    "OFX-MISMATCH", "20260213", "10.00", "Mismatch"
                ),
            ).encode("utf-8"),
        )
    assert account_mismatch.value.status_code == 422

    duplicate_fitid = OFX_TEMPLATE.format(
        account_number=account_number,
        transactions=(
            _ofx_transaction("OFX-DUP", "20260213", "10.00", "First")
            + _ofx_transaction("OFX-DUP", "20260214", "11.00", "Second")
        ),
    ).encode("utf-8")
    with pytest.raises(HTTPException, match="duplicate external_id") as duplicate:
        await service.import_ofx(
            organization_id,
            "import-tester",
            bank_profile_id,
            "ofx-import-duplicate",
            "duplicate.ofx",
            duplicate_fitid,
        )
    assert duplicate.value.status_code == 422

    unsafe_xml = b"""<?xml version="1.0"?>
<!DOCTYPE OFX [<!ENTITY secret SYSTEM "file:///etc/passwd">]>
<OFX><BANKMSGSRSV1/></OFX>"""
    with pytest.raises(HTTPException, match="valid safe XML") as unsafe:
        await service.import_ofx(
            organization_id,
            "import-tester",
            bank_profile_id,
            "ofx-import-unsafe",
            "unsafe.ofx",
            unsafe_xml,
        )
    assert unsafe.value.status_code == 422
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


MT940_TEMPLATE = """:20:STATEMENT-001
:25:{account_number}
:28C:00001/001
:60F:C260214XOF1000,00
{transactions}
:62F:C260216XOF1115,00
"""


def _mt940_transaction(
    value_date: str,
    entry_date: str,
    mark: str,
    amount: str,
    reference: str,
    narrative: str,
) -> str:
    return f":61:{value_date}{entry_date}{mark}{amount}NMSCREMIT//{reference}\n:86:{narrative}"


@pytest.mark.asyncio
async def test_mt940_import_normalizes_credit_debit_idempotently_and_audits(
    db_session: AsyncSession,
) -> None:
    from app.models.treasury.bank_account import TreasuryBankAccount

    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    bank_account = await db_session.get(TreasuryBankAccount, bank_profile_id)
    assert bank_account is not None
    content = MT940_TEMPLATE.format(
        account_number=bank_account.account_number,
        transactions=(
            _mt940_transaction(
                "260215", "0215", "C", "120,50", "MT940-CR-001", "Customer collection"
            )
            + "\n"
            + _mt940_transaction(
                "260216", "0216", "D", "5,50", "MT940-DB-002", "Bank fee"
            )
        ),
    ).encode("utf-8")
    service = BankStatementImportService(db_session)
    first = await service.import_mt940(
        organization_id,
        "import-tester",
        bank_profile_id,
        "mt940-import-001",
        "february.mt940",
        content,
    )
    repeated = await service.import_mt940(
        organization_id,
        "import-tester",
        bank_profile_id,
        "mt940-import-001",
        "february.mt940",
        content,
    )

    assert first.id == repeated.id
    assert first.format_version == "MT940_V1"
    assert first.imported_count == 2
    assert first.duplicate_count == 0
    rows = list(
        await db_session.execute(
            select(
                BankTransaction.external_id,
                BankTransaction.transaction_date,
                BankTransaction.value_date,
                BankTransaction.amount,
                BankTransaction.description,
            )
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.external_id.in_(
                    ["MT940:MT940-CR-001", "MT940:MT940-DB-002"]
                ),
            )
            .order_by(BankTransaction.external_id)
        )
    )
    assert rows == [
        (
            "MT940:MT940-CR-001",
            date(2026, 2, 15),
            date(2026, 2, 15),
            Decimal("120.50"),
            "Customer collection",
        ),
        (
            "MT940:MT940-DB-002",
            date(2026, 2, 16),
            date(2026, 2, 16),
            Decimal("-5.50"),
            "Bank fee",
        ),
    ]
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


@pytest.mark.asyncio
async def test_mt940_import_rejects_account_mismatch_duplicate_reference_and_rolls_back(
    db_session: AsyncSession,
) -> None:
    from app.models.treasury.bank_account import TreasuryBankAccount

    organization, _, bank_profile, _, _, _ = await _context(db_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    bank_account = await db_session.get(TreasuryBankAccount, bank_profile_id)
    assert bank_account is not None
    account_number = bank_account.account_number
    service = BankStatementImportService(db_session)

    with pytest.raises(HTTPException, match="account identifier") as mismatch:
        await service.import_mt940(
            organization_id,
            "import-tester",
            bank_profile_id,
            "mt940-import-mismatch",
            "mismatch.mt940",
            MT940_TEMPLATE.format(
                account_number="OTHER-ACCOUNT",
                transactions=_mt940_transaction(
                    "260215", "0215", "C", "10,00", "MT940-MISMATCH", "Mismatch"
                ),
            ).encode("utf-8"),
        )
    assert mismatch.value.status_code == 422

    duplicate_reference = MT940_TEMPLATE.format(
        account_number=account_number,
        transactions=(
            _mt940_transaction("260215", "0215", "C", "10,00", "MT940-DUP", "First")
            + "\n"
            + _mt940_transaction("260216", "0216", "C", "11,00", "MT940-DUP", "Second")
        ),
    ).encode("utf-8")
    with pytest.raises(HTTPException, match="duplicate external_id") as duplicate:
        await service.import_mt940(
            organization_id,
            "import-tester",
            bank_profile_id,
            "mt940-import-duplicate",
            "duplicate.mt940",
            duplicate_reference,
        )
    assert duplicate.value.status_code == 422
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
