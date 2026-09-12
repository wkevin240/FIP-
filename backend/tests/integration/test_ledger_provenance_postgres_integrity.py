import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_ledger_posting_must_match_posted_journal_source() -> None:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        pytest.skip("PostgreSQL integration environment is not configured")

    connection = await asyncpg.connect(
        host=server,
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "fip_user"),
        password=os.getenv("POSTGRES_PASSWORD", "fip_password"),
        database=os.getenv("POSTGRES_DB", "fip_db"),
    )
    try:
        definition = await connection.fetchval(
            """
            SELECT pg_get_triggerdef(oid)
            FROM pg_trigger
            WHERE tgrelid = 'ledger_postings'::regclass
              AND tgname = 'trg_ledger_postings_validate_provenance'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE INSERT" in definition
        assert "fip_ledger_posting_validate_provenance" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-org', 'integration-only', TRUE, NOW(), NOW()),
                        ('ledger-provenance-other-org', 'integration-only-other', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-year', '2026', '2026-01-01', '2026-12-31', 'ledger-provenance-org', 'OPEN', NOW(), NOW()),
                        ('ledger-provenance-other-year', '2026', '2026-01-01', '2026-12-31', 'ledger-provenance-other-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'ledger-provenance-year', 'ledger-provenance-org', NOW(), NOW()),
                        ('ledger-provenance-other-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'ledger-provenance-other-year', 'ledger-provenance-other-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-debit', 'ledger-provenance-org', 'TEST-D', 'Debit source', TRUE, 'TEST', 1, '/', NOW(), NOW()),
                        ('ledger-provenance-credit', 'ledger-provenance-org', 'TEST-C', 'Credit source', TRUE, 'TEST', 1, '/', NOW(), NOW()),
                        ('ledger-provenance-other-account', 'ledger-provenance-other-org', 'TEST-X', 'Other tenant', TRUE, 'TEST', 1, '/', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-entry', 'ledger-provenance-org', 'ledger-provenance-period', '2026-01-10', 'integration-only', 'DRAFT', 'ledger-provenance-key', repeat('e', 64), NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-debit-line', 'ledger-provenance-entry', 1, 'ledger-provenance-debit', 100.00, 0.00, NOW(), NOW()),
                        ('ledger-provenance-credit-line', 'ledger-provenance-entry', 2, 'ledger-provenance-credit', 0.00, 100.00, NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as draft_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO ledger_postings
                                (id, organization_id, fiscal_period_id, journal_entry_id, journal_entry_line_id, account_id, posting_date, line_number, description, debit, credit, created_at, updated_at)
                            VALUES
                                ('ledger-provenance-draft', 'ledger-provenance-org', 'ledger-provenance-period', 'ledger-provenance-entry', 'ledger-provenance-debit-line', 'ledger-provenance-debit', '2026-01-10', 1, 'integration-only', 100.00, 0.00, NOW(), NOW())
                            """
                        )
                assert draft_error.value.sqlstate == "23514"

                await connection.execute(
                    "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'ledger-provenance-entry'"
                )

                with pytest.raises(asyncpg.PostgresError) as mismatch_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO ledger_postings
                                (id, organization_id, fiscal_period_id, journal_entry_id, journal_entry_line_id, account_id, posting_date, line_number, description, debit, credit, created_at, updated_at)
                            VALUES
                                ('ledger-provenance-mismatch', 'ledger-provenance-other-org', 'ledger-provenance-other-period', 'ledger-provenance-entry', 'ledger-provenance-debit-line', 'ledger-provenance-other-account', '2026-01-10', 1, 'integration-only', 100.00, 0.00, NOW(), NOW())
                            """
                        )
                assert mismatch_error.value.sqlstate == "23514"

                with pytest.raises(asyncpg.PostgresError) as amount_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO ledger_postings
                                (id, organization_id, fiscal_period_id, journal_entry_id, journal_entry_line_id, account_id, posting_date, line_number, description, debit, credit, created_at, updated_at)
                            VALUES
                                ('ledger-provenance-amount', 'ledger-provenance-org', 'ledger-provenance-period', 'ledger-provenance-entry', 'ledger-provenance-debit-line', 'ledger-provenance-debit', '2026-01-10', 1, 'integration-only', 99.00, 0.00, NOW(), NOW())
                            """
                        )
                assert amount_error.value.sqlstate == "23514"

                await connection.execute(
                    """
                    INSERT INTO ledger_postings
                        (id, organization_id, fiscal_period_id, journal_entry_id, journal_entry_line_id, account_id, posting_date, line_number, description, debit, credit, created_at, updated_at)
                    VALUES
                        ('ledger-provenance-valid', 'ledger-provenance-org', 'ledger-provenance-period', 'ledger-provenance-entry', 'ledger-provenance-debit-line', 'ledger-provenance-debit', '2026-01-10', 1, 'integration-only', 100.00, 0.00, NOW(), NOW())
                    """
                )
                count = await connection.fetchval(
                    "SELECT COUNT(*) FROM ledger_postings WHERE id = 'ledger-provenance-valid'"
                )
                assert count == 1
                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
