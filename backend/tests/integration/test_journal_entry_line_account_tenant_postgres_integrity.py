import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_journal_entry_line_account_stays_within_journal_organization() -> None:
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
            WHERE tgrelid = 'journal_entry_lines'::regclass
              AND tgname = 'trg_journal_entry_lines_validate_account_tenant'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF journal_entry_id, account_id" in definition
        assert "fip_journal_entry_line_validate_account_tenant" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES
                        ('journal-line-org', 'integration-only', TRUE, NOW(), NOW()),
                        ('journal-line-other', 'integration-only-other', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts
                        (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES
                        ('journal-line-account', 'journal-line-org', 'JL-1', 'integration-only', TRUE, 'TEST', 1, '/JL-1/', NOW(), NOW()),
                        ('journal-line-other-account', 'journal-line-other', 'JL-2', 'integration-only', TRUE, 'TEST', 1, '/JL-2/', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years
                        (id, organization_id, name, start_date, end_date, status, created_at, updated_at)
                    VALUES
                        ('journal-line-year', 'journal-line-org', 'integration-only-2026', '2026-01-01', '2026-12-31', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods
                        (id, organization_id, fiscal_year_id, name, start_date, end_date, status, created_at, updated_at)
                    VALUES
                        ('journal-line-period', 'journal-line-org', 'journal-line-year', 'integration-only', '2026-01-01', '2026-12-31', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_by)
                    VALUES
                        ('journal-line-entry', 'journal-line-org', 'journal-line-period', '2026-06-30', 'integration-only', 'DRAFT', 'journal-line-test', repeat('a', 64), 'journal-line-test-creator')
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as cross_org_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO journal_entry_lines
                                (id, journal_entry_id, line_number, account_id, description, debit, credit)
                            VALUES
                                ('journal-line-cross-org', 'journal-line-entry', 1, 'journal-line-other-account', 'integration-only', 100.00, 0.00)
                            """
                        )
                assert cross_org_error.value.sqlstate == "23514"

                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, description, debit, credit)
                    VALUES
                        ('journal-line-valid', 'journal-line-entry', 1, 'journal-line-account', 'integration-only', 100.00, 0.00)
                    """
                )
                row = await connection.fetchrow(
                    "SELECT journal_entry_id, account_id FROM journal_entry_lines WHERE id = 'journal-line-valid'"
                )
                assert row is not None
                assert row["journal_entry_id"] == "journal-line-entry"
                assert row["account_id"] == "journal-line-account"

                with pytest.raises(asyncpg.PostgresError) as update_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            UPDATE journal_entry_lines
                            SET account_id = 'journal-line-other-account'
                            WHERE id = 'journal-line-valid'
                            """
                        )
                assert update_error.value.sqlstate == "23514"

                row = await connection.fetchrow(
                    "SELECT account_id FROM journal_entry_lines WHERE id = 'journal-line-valid'"
                )
                assert row is not None
                assert row["account_id"] == "journal-line-account"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
