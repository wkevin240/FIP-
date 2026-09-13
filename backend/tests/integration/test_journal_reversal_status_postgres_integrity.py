import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_reversed_status_requires_posted_reversal() -> None:
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
              AND tgname = 'trg_journal_reversal_status_integrity'
            """
        )
        assert definition is not None
        assert "DEFERRABLE INITIALLY DEFERRED" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('reversal-status-org', 'integration-only', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('reversal-status-year', '2026', '2026-01-01', '2026-12-31', 'reversal-status-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('reversal-status-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'reversal-status-year', 'reversal-status-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES ('reversal-status-account', 'reversal-status-org', 'TEST-STATUS', 'Integration account', TRUE, 'TEST', 1, '/', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                    VALUES
                        ('reversal-status-original', 'reversal-status-org', 'reversal-status-period', '2026-01-10', 'integration-only', 'DRAFT', 'reversal-status-original-key', repeat('a', 64), NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('reversal-status-original-debit', 'reversal-status-original', 1, 'reversal-status-account', 100.00, 0.00, NOW(), NOW()),
                        ('reversal-status-original-credit', 'reversal-status-original', 2, 'reversal-status-account', 0.00, 100.00, NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    await connection.execute(
                        "UPDATE journal_entries SET status = 'REVERSED' WHERE id = 'reversal-status-original'"
                    )
                assert error.value.sqlstate == "23514"

                await connection.execute(
                    "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'reversal-status-original'"
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, reversal_of_id, created_at, updated_at)
                    VALUES
                        ('reversal-status-reversal', 'reversal-status-org', 'reversal-status-period', '2026-01-10', 'integration-only', 'DRAFT', 'reversal-status-reversal-key', repeat('b', 64), 'reversal-status-original', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('reversal-status-reversal-debit', 'reversal-status-reversal', 1, 'reversal-status-account', 0.00, 100.00, NOW(), NOW()),
                        ('reversal-status-reversal-credit', 'reversal-status-reversal', 2, 'reversal-status-account', 100.00, 0.00, NOW(), NOW())
                    """
                )
                await connection.execute(
                    "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'reversal-status-reversal'"
                )
                await connection.execute(
                    "UPDATE journal_entries SET status = 'REVERSED' WHERE id = 'reversal-status-original'"
                )
                status = await connection.fetchval(
                    "SELECT status::text FROM journal_entries WHERE id = 'reversal-status-original'"
                )
                assert status == "REVERSED"

                with pytest.raises(asyncpg.PostgresError) as error:
                    await connection.execute(
                        "UPDATE journal_entries SET status = 'DRAFT' WHERE id = 'reversal-status-reversal'"
                    )
                assert error.value.sqlstate == "23514"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
