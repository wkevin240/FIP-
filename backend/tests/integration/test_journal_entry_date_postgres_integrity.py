import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_journal_entry_date_must_fall_within_fiscal_period() -> None:
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
            WHERE tgrelid = 'journal_entries'::regclass
              AND tgname = 'trg_journal_entries_validate_period_date'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF fiscal_period_id, organization_id, entry_date" in definition
        assert "fip_journal_entry_validate_period_date" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('entry-date-org', 'integration-only', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('entry-date-year', '2026', '2026-01-01', '2026-12-31', 'entry-date-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('entry-date-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'entry-date-year', 'entry-date-org', NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO journal_entries
                                (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_by, created_at, updated_at)
                            VALUES
                                ('entry-date-outside', 'entry-date-org', 'entry-date-period', '2026-02-01', 'integration-only', 'DRAFT', 'entry-date-outside-key', repeat('c', 64), 'entry-date-test-creator', NOW(), NOW())
                            """
                        )
                assert error.value.sqlstate == "23514"

                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_by, created_at, updated_at)
                    VALUES
                        ('entry-date-inside', 'entry-date-org', 'entry-date-period', '2026-01-31', 'integration-only', 'DRAFT', 'entry-date-inside-key', repeat('d', 64), 'entry-date-test-creator', NOW(), NOW())
                    """
                )

                status = await connection.fetchval(
                    "SELECT status::text FROM journal_entries WHERE id = 'entry-date-inside'"
                )
                assert status == "DRAFT"

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            "UPDATE journal_entries SET entry_date = '2026-02-01' WHERE id = 'entry-date-inside'"
                        )
                assert error.value.sqlstate == "23514"

                entry_date = await connection.fetchval(
                    "SELECT entry_date FROM journal_entries WHERE id = 'entry-date-inside'"
                )
                assert str(entry_date) == "2026-01-31"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
