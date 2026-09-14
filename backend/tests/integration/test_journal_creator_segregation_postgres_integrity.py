import os

import asyncpg
import pytest


async def _connect() -> asyncpg.Connection:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        pytest.skip("PostgreSQL integration environment is not configured")
    return await asyncpg.connect(
        host=server,
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "fip_user"),
        password=os.getenv("POSTGRES_PASSWORD", "fip_password"),
        database=os.getenv("POSTGRES_DB", "fip_db"),
    )


@pytest.mark.asyncio
async def test_creator_cannot_post_direct_sql_but_distinct_actor_can() -> None:
    connection = await _connect()
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ('sod-org', 'integration-only', TRUE)"
            )
            await connection.execute(
                """
                INSERT INTO fiscal_years (id, organization_id, name, start_date, end_date, status)
                VALUES ('sod-year', 'sod-org', 'integration-only', DATE '2026-01-01', DATE '2026-12-31', 'OPEN')
                """
            )
            await connection.execute(
                """
                INSERT INTO fiscal_periods (id, organization_id, fiscal_year_id, name, start_date, end_date, status)
                VALUES ('sod-period', 'sod-org', 'sod-year', 'integration-only', DATE '2026-01-01', DATE '2026-01-31', 'OPEN')
                """
            )
            await connection.execute(
                """
                INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path)
                VALUES
                    ('sod-debit', 'sod-org', 'TEST-D', 'integration-only', TRUE, 'EXPENSE', 1, '/'),
                    ('sod-credit', 'sod-org', 'TEST-C', 'integration-only-credit', TRUE, 'LIABILITY', 1, '/')
                """
            )
            await connection.execute(
                """
                INSERT INTO journal_entries (
                    id, organization_id, fiscal_period_id, entry_date, description,
                    status, idempotency_key, idempotency_hash, created_by, posted_at, posted_by
                )
                VALUES (
                    'sod-entry', 'sod-org', 'sod-period', DATE '2026-01-15',
                    'integration-only', 'DRAFT', 'sod-key', repeat('b', 64),
                    'creator-1', NULL, NULL
                )
                """
            )
            await connection.execute(
                """
                INSERT INTO journal_entry_lines
                    (id, journal_entry_id, line_number, account_id, debit, credit)
                VALUES
                    ('sod-line-1', 'sod-entry', 1, 'sod-debit', 100.00, 0.00),
                    ('sod-line-2', 'sod-entry', 2, 'sod-credit', 0.00, 100.00)
                """
            )

            with pytest.raises(asyncpg.PostgresError) as creator_change_error:
                async with connection.transaction():
                    await connection.execute(
                        "UPDATE journal_entries SET created_by = 'poster-1' WHERE id = 'sod-entry'"
                    )
            assert creator_change_error.value.sqlstate == "42501"
            creator = await connection.fetchval(
                "SELECT created_by FROM journal_entries WHERE id = 'sod-entry'"
            )
            assert creator == "creator-1"

            with pytest.raises(asyncpg.PostgresError) as self_post_error:
                async with connection.transaction():
                    await connection.execute(
                        """
                        UPDATE journal_entries
                        SET status = 'POSTED',
                            posted_at = TIMESTAMP '2026-01-15 12:00:00',
                            posted_by = 'creator-1'
                        WHERE id = 'sod-entry'
                        """
                    )
            assert self_post_error.value.sqlstate == "42501"
            state = await connection.fetchrow(
                "SELECT status, posted_by FROM journal_entries WHERE id = 'sod-entry'"
            )
            assert state["status"] == "DRAFT"
            assert state["posted_by"] is None

            await connection.execute(
                """
                UPDATE journal_entries
                SET status = 'POSTED',
                    posted_at = TIMESTAMP '2026-01-15 12:00:00',
                    posted_by = 'poster-1'
                WHERE id = 'sod-entry'
                """
            )
            state = await connection.fetchrow(
                "SELECT status, created_by, posted_by FROM journal_entries WHERE id = 'sod-entry'"
            )
            assert state["status"] == "POSTED"
            assert state["created_by"] == "creator-1"
            assert state["posted_by"] == "poster-1"

            await connection.execute("UPDATE journal_entries SET status = 'DRAFT' WHERE id = 'sod-entry'")
            await connection.execute("DELETE FROM journal_entry_lines WHERE journal_entry_id = 'sod-entry'")
            await connection.execute("DELETE FROM journal_entries WHERE id = 'sod-entry'")
            await connection.execute("DELETE FROM accounts WHERE organization_id = 'sod-org'")
            await connection.execute("DELETE FROM fiscal_periods WHERE organization_id = 'sod-org'")
            await connection.execute("DELETE FROM fiscal_years WHERE id = 'sod-year'")
            await connection.execute("DELETE FROM organizations WHERE id = 'sod-org'")
    finally:
        await connection.close()
