import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_posted_journal_lines_and_entry_cannot_be_mutated_or_deleted() -> None:
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
        async with connection.transaction():
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
                    'integration-only', 'POSTED', 'immutability-key', repeat('a', 64), 'integration'
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
