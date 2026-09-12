import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_journal_entries_cannot_bypass_closed_fiscal_periods() -> None:
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
              AND tgname = 'trg_journal_entries_require_open_period'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF fiscal_period_id, organization_id, status" in definition
        assert "fip_journal_entry_require_open_period" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('period-guard-org', 'period-guard-org', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('period-guard-year', '2026', '2026-01-01', '2026-12-31', 'period-guard-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('period-guard-period', 'January 2026', '2026-01-01', '2026-01-31', 'CLOSED', 'period-guard-year', 'period-guard-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES ('period-guard-account', 'period-guard-org', 'TEST-PG', 'Period guard account', TRUE, 'TEST', 1, '/', NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO journal_entries
                                (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                            VALUES
                                ('period-guard-insert', 'period-guard-org', 'period-guard-period', '2026-01-10', 'Closed period insert proof', 'DRAFT', 'period-guard-insert-key', repeat('a', 64), NOW(), NOW())
                            """
                        )
                assert error.value.sqlstate == "23514"

                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('period-guard-open-period', 'February 2026', '2026-02-01', '2026-02-28', 'OPEN', 'period-guard-year', 'period-guard-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                    VALUES
                        ('period-guard-post', 'period-guard-org', 'period-guard-open-period', '2026-02-10', 'Closed period posting proof', 'DRAFT', 'period-guard-post-key', repeat('b', 64), NOW(), NOW())
                    """
                )

                await connection.execute(
                    "UPDATE fiscal_periods SET status = 'CLOSED' WHERE id = 'period-guard-open-period'"
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'period-guard-post'"
                        )
                assert error.value.sqlstate == "23514"

                status = await connection.fetchval(
                    "SELECT status::text FROM journal_entries WHERE id = 'period-guard-post'"
                )
                assert status == "DRAFT"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
