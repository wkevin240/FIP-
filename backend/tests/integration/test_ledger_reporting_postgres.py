import os
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.dependencies import get_db
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.core.enums.users import MembershipRole
from app.core.security import create_access_token
from app.main import create_application
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.models.membership import OrganizationMembership
from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_ledger_reporting_api_uses_migrated_postgres_contract() -> None:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        pytest.skip("PostgreSQL integration environment is not configured")

    database_uri = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'fip_user')}"
        f":{os.getenv('POSTGRES_PASSWORD', 'fip_password')}@{server}"
        f":{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'fip_db')}"
    )
    engine = create_async_engine(database_uri, pool_pre_ping=True)
    application = create_application()

    organization_id = "ledger-reporting-org"
    other_organization_id = "ledger-reporting-other-org"
    reader_id = "ledger-reporting-reader"
    year_id = "ledger-reporting-year"
    period_id = "ledger-reporting-period"
    other_period_id = "ledger-reporting-other-period"
    debit_account_id = "ledger-reporting-debit"
    credit_account_id = "ledger-reporting-credit"
    other_account_id = "ledger-reporting-other-account"
    entry_id = "ledger-reporting-entry"
    other_entry_id = "ledger-reporting-other-entry"
    debit_line_id = "ledger-reporting-debit-line"
    credit_line_id = "ledger-reporting-credit-line"
    other_debit_line_id = "ledger-reporting-other-debit-line"
    other_credit_line_id = "ledger-reporting-other-credit-line"
    debit_posting_id = "ledger-reporting-debit-posting"
    credit_posting_id = "ledger-reporting-credit-posting"
    other_debit_posting_id = "ledger-reporting-other-debit-posting"
    other_credit_posting_id = "ledger-reporting-other-credit-posting"

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db():
            yield session

        application.dependency_overrides[get_db] = override_get_db

        try:
            session.add_all(
                [
                    Organization(id=organization_id, name="ledger-reporting-org"),
                    Organization(id=other_organization_id, name="ledger-reporting-other-org"),
                    User(
                        id=reader_id,
                        email="ledger-reporting-reader@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    FiscalYear(
                        id=year_id,
                        organization_id=organization_id,
                        name="2026",
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 12, 31),
                        status=FiscalYearStatus.OPEN,
                    ),
                    FiscalPeriod(
                        id=period_id,
                        organization_id=organization_id,
                        fiscal_year_id=year_id,
                        name="January 2026",
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 1, 31),
                        status=FiscalPeriodStatus.OPEN,
                    ),
                    FiscalPeriod(
                        id=other_period_id,
                        organization_id=other_organization_id,
                        fiscal_year_id=year_id,
                        name="January 2026 other tenant",
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 1, 31),
                        status=FiscalPeriodStatus.OPEN,
                    ),
                    Account(
                        id=debit_account_id,
                        organization_id=organization_id,
                        code="601-TEST",
                        name="Reporting debit",
                        account_type="EXPENSE",
                        level=1,
                        path="/",
                    ),
                    Account(
                        id=credit_account_id,
                        organization_id=organization_id,
                        code="401-TEST",
                        name="Reporting credit",
                        account_type="LIABILITY",
                        level=1,
                        path="/",
                    ),
                    Account(
                        id=other_account_id,
                        organization_id=other_organization_id,
                        code="601-OTHER",
                        name="Other tenant account",
                        account_type="EXPENSE",
                        level=1,
                        path="/",
                    ),
                    OrganizationMembership(
                        user_id=reader_id,
                        organization_id=organization_id,
                        role=MembershipRole.ACCOUNTANT.value,
                        is_active=True,
                    ),
                ]
            )
            await session.flush()

            posted_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
            session.add_all(
                [
                    JournalEntry(
                        id=entry_id,
                        organization_id=organization_id,
                        fiscal_period_id=period_id,
                        entry_date=date(2026, 1, 15),
                        description="Reporting integration entry",
                        status=JournalEntryStatus.POSTED,
                        idempotency_key="ledger-reporting-entry-key",
                        idempotency_hash="a" * 64,
                        created_by=reader_id,
                        posted_at=posted_at,
                        posted_by="ledger-reporting-poster",
                    ),
                    JournalEntry(
                        id=other_entry_id,
                        organization_id=other_organization_id,
                        fiscal_period_id=other_period_id,
                        entry_date=date(2026, 1, 15),
                        description="Other tenant integration entry",
                        status=JournalEntryStatus.POSTED,
                        idempotency_key="ledger-reporting-other-entry-key",
                        idempotency_hash="b" * 64,
                        created_by=reader_id,
                        posted_at=posted_at,
                        posted_by="ledger-reporting-poster",
                    ),
                ]
            )
            await session.flush()

            session.add_all(
                [
                    JournalEntryLine(
                        id=debit_line_id,
                        journal_entry_id=entry_id,
                        line_number=1,
                        account_id=debit_account_id,
                        debit=Decimal("125.00"),
                        credit=Decimal("0.00"),
                    ),
                    JournalEntryLine(
                        id=credit_line_id,
                        journal_entry_id=entry_id,
                        line_number=2,
                        account_id=credit_account_id,
                        debit=Decimal("0.00"),
                        credit=Decimal("125.00"),
                    ),
                    JournalEntryLine(
                        id=other_debit_line_id,
                        journal_entry_id=other_entry_id,
                        line_number=1,
                        account_id=other_account_id,
                        debit=Decimal("900.00"),
                        credit=Decimal("0.00"),
                    ),
                    JournalEntryLine(
                        id=other_credit_line_id,
                        journal_entry_id=other_entry_id,
                        line_number=2,
                        account_id=other_account_id,
                        debit=Decimal("0.00"),
                        credit=Decimal("900.00"),
                    ),
                ]
            )
            await session.flush()

            session.add_all(
                [
                    LedgerPosting(
                        id=debit_posting_id,
                        organization_id=organization_id,
                        fiscal_period_id=period_id,
                        journal_entry_id=entry_id,
                        journal_entry_line_id=debit_line_id,
                        account_id=debit_account_id,
                        posting_date=date(2026, 1, 15),
                        line_number=1,
                        description="Reporting integration entry",
                        debit=Decimal("125.00"),
                        credit=Decimal("0.00"),
                    ),
                    LedgerPosting(
                        id=credit_posting_id,
                        organization_id=organization_id,
                        fiscal_period_id=period_id,
                        journal_entry_id=entry_id,
                        journal_entry_line_id=credit_line_id,
                        account_id=credit_account_id,
                        posting_date=date(2026, 1, 15),
                        line_number=2,
                        description="Reporting integration entry",
                        debit=Decimal("0.00"),
                        credit=Decimal("125.00"),
                    ),
                    LedgerPosting(
                        id=other_debit_posting_id,
                        organization_id=other_organization_id,
                        fiscal_period_id=other_period_id,
                        journal_entry_id=other_entry_id,
                        journal_entry_line_id=other_debit_line_id,
                        account_id=other_account_id,
                        posting_date=date(2026, 1, 15),
                        line_number=1,
                        description="Other tenant integration entry",
                        debit=Decimal("900.00"),
                        credit=Decimal("0.00"),
                    ),
                    LedgerPosting(
                        id=other_credit_posting_id,
                        organization_id=other_organization_id,
                        fiscal_period_id=other_period_id,
                        journal_entry_id=other_entry_id,
                        journal_entry_line_id=other_credit_line_id,
                        account_id=other_account_id,
                        posting_date=date(2026, 1, 15),
                        line_number=2,
                        description="Other tenant integration entry",
                        debit=Decimal("0.00"),
                        credit=Decimal("900.00"),
                    ),
                ]
            )
            await session.flush()

            reader_token = create_access_token(reader_id, organization_id)
            headers = {"Authorization": f"Bearer {reader_token}"}
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                trial_response = await client.get(
                    "/api/v1/accounting/ledger/trial-balance",
                    params={"fiscal_period_id": period_id},
                    headers=headers,
                )
                assert trial_response.status_code == 200, trial_response.text
                rows = trial_response.json()
                assert [row["account_id"] for row in rows] == [credit_account_id, debit_account_id]
                assert {row["account_id"] for row in rows} == {debit_account_id, credit_account_id}
                debit_row = next(row for row in rows if row["account_id"] == debit_account_id)
                credit_row = next(row for row in rows if row["account_id"] == credit_account_id)
                assert Decimal(debit_row["debit"]) == Decimal("125.00")
                assert Decimal(debit_row["credit"]) == Decimal("0.00")
                assert Decimal(debit_row["balance"]) == Decimal("125.00")
                assert Decimal(credit_row["debit"]) == Decimal("0.00")
                assert Decimal(credit_row["credit"]) == Decimal("125.00")
                assert Decimal(credit_row["balance"]) == Decimal("-125.00")

                control_response = await client.get(
                    "/api/v1/accounting/ledger/trial-balance/control",
                    params={"fiscal_period_id": period_id},
                    headers=headers,
                )
                assert control_response.status_code == 200, control_response.text
                control = control_response.json()
                assert control["row_count"] == 2
                assert Decimal(control["total_debit"]) == Decimal("125.00")
                assert Decimal(control["total_credit"]) == Decimal("125.00")
                assert Decimal(control["balance_difference"]) == Decimal("0.00")
                assert control["is_balanced"] is True

                reconciliation_response = await client.get(
                    "/api/v1/accounting/ledger/reconciliation",
                    params={"fiscal_period_id": period_id},
                    headers=headers,
                )
                assert reconciliation_response.status_code == 200, reconciliation_response.text
                reconciliation = reconciliation_response.json()
                assert reconciliation["expected_journal_lines"] == 2
                assert reconciliation["actual_ledger_postings"] == 2
                assert reconciliation["missing_postings"] == []
                assert reconciliation["orphan_postings"] == []
                assert reconciliation["mismatched_postings"] == []
                assert reconciliation["is_reconciled"] is True

                cross_tenant_response = await client.get(
                    "/api/v1/accounting/ledger/trial-balance",
                    params={"fiscal_period_id": other_period_id},
                    headers=headers,
                )
                assert cross_tenant_response.status_code == 404
        finally:
            application.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
            await engine.dispose()
