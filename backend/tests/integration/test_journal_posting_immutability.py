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


async def _seed_postable_journal(connection: asyncpg.Connection) -> None:
    await connection.execute(
        "INSERT INTO organizations (id, name, is_active) VALUES ('immutability-org', 'integration-only', TRUE)"
    )
    await connection.execute(
        """
        INSERT INTO fiscal_years (id, organization_id, name, start_date, end_date, status)
        VALUES ('immutability-year', 'immutability-org', 'integration-only', DATE '2026-01-01', DATE '2026-12-31', 'OPEN')
        """
    )
    await connection.execute(
        """
        INSERT INTO fiscal_periods (id, organization_id, fiscal_year_id, name, start_date, end_date, status)
        VALUES ('immutability-period', 'immutability-org', 'immutability-year', 'integration-only', DATE '2026-01-01', DATE '2026-01-31', 'OPEN')
        """
    )
    await connection.execute(
        """
        INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path)
        VALUES ('immutability-account', 'immutability-org', '999', 'integration-only', TRUE, 'EXPENSE', 1, '/')
        """
    )
    await connection.execute(
        """
        INSERT INTO journal_entries (
            id, organization_id, fiscal_period_id, entry_date, description,
            status, idempotency_key, idempotency_hash, posted_by
        )
        VALUES (
            'immutability-entry', 'immutability-org', 'immutability-period', DATE '2026-01-15',
            'integration-only', 'DRAFT', 'immutability-key', repeat('a', 64), 'integration'
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO journal_entry_lines (
            id, journal_entry_id, line_number, account_id, description, debit, credit
        )
        VALUES (
            'immutability-line', 'immutability-entry', 1, 'immutability-account',
            'integration-only', 100.00, 0.00
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path)
        VALUES ('immutability-offset-account', 'immutability-org', '998', 'integration-only-offset', TRUE, 'ASSET', 1, '/')
        """
    )
    await connection.execute(
        """
        INSERT INTO journal_entry_lines (
            id, journal_entry_id, line_number, account_id, description, debit, credit
        )
        VALUES (
            'immutability-offset-line', 'immutability-entry', 2, 'immutability-offset-account',
            'integration-only-offset', 0.00, 100.00
        )
        """
    )
    await connection.execute(
        "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'immutability-entry'"
    )


@pytest.mark.asyncio
async def test_posted_journal_lines_and_entry_cannot_be_mutated_or_deleted() -> None:
    connection = await _connect()
    try:
        async with connection.transaction():
            await _seed_postable_journal(connection)

            with pytest.raises(asyncpg.PostgresError) as update_error:
                await connection.execute(
                    "UPDATE journal_entry_lines SET description = 'tampered' WHERE id = 'immutability-line'"
                )
            assert update_error.value.sqlstate == "55000"

            row = await connection.fetchrow(
                "SELECT description, debit, credit FROM journal_entry_lines WHERE id = 'immutability-line'"
            )
            assert row["description"] == "integration-only"
            assert row["debit"] == 100
            assert row["credit"] == 0

            with pytest.raises(asyncpg.PostgresError) as delete_line_error:
                await connection.execute("DELETE FROM journal_entry_lines WHERE id = 'immutability-line'")
            assert delete_line_error.value.sqlstate == "55000"

            with pytest.raises(asyncpg.PostgresError) as delete_entry_error:
                await connection.execute("DELETE FROM journal_entries WHERE id = 'immutability-entry'")
            assert delete_entry_error.value.sqlstate == "55000"

            assert await connection.fetchval(
                "SELECT count(*) FROM journal_entry_lines WHERE id = 'immutability-line'"
            ) == 1
            assert await connection.fetchval(
                "SELECT count(*) FROM journal_entries WHERE id = 'immutability-entry'"
            ) == 1
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_journal_line_mutation_trigger_locks_parent_journal() -> None:
    connection = await _connect()
    locker = await _connect()
    try:
        async with connection.transaction():
            await _seed_postable_journal(connection)
            await locker.execute("BEGIN")
            await locker.execute(
                "SELECT id FROM journal_entries WHERE id = 'immutability-entry' FOR UPDATE"
            )

            await connection.execute("SET LOCAL statement_timeout = '100ms'")
            with pytest.raises(asyncpg.PostgresError) as lock_error:
                await connection.execute(
                    "UPDATE journal_entry_lines SET description = 'blocked' WHERE id = 'immutability-line'"
                )
            assert lock_error.value.sqlstate == "57014"

            await locker.execute("ROLLBACK")
    finally:
        await locker.close()
        await connection.close()
