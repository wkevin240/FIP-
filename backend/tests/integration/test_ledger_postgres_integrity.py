import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_ledger_postings_are_database_immutable() -> None:
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
        triggers = await connection.fetch(
            """
            SELECT tgname, pg_get_triggerdef(oid) AS definition
            FROM pg_trigger
            WHERE tgrelid = 'ledger_postings'::regclass
              AND NOT tgisinternal
            ORDER BY tgname
            """
        )
        definitions = {row["tgname"]: row["definition"] for row in triggers}

        assert "trg_ledger_postings_no_update" in definitions
        assert "trg_ledger_postings_no_delete" in definitions
        assert "BEFORE UPDATE" in definitions["trg_ledger_postings_no_update"]
        assert "BEFORE DELETE" in definitions["trg_ledger_postings_no_delete"]
        assert "fip_ledger_postings_append_only" in definitions["trg_ledger_postings_no_update"]
        assert "fip_ledger_postings_append_only" in definitions["trg_ledger_postings_no_delete"]

        await connection.execute(
            """
            INSERT INTO organizations (id, name, is_active, created_at, updated_at)
            VALUES ('ledger-integrity-org', 'ledger-integrity-org', TRUE, NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
            VALUES ('ledger-integrity-year', '2026', '2026-01-01', '2026-12-31', 'ledger-integrity-org', 'OPEN', NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
            VALUES ('ledger-integrity-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'ledger-integrity-year', 'ledger-integrity-org', NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
            VALUES
                ('ledger-integrity-debit-account', 'ledger-integrity-org', 'TEST-D', 'Ledger integrity debit', TRUE, 'TEST', 1, '/', NOW(), NOW()),
                ('ledger-integrity-credit-account', 'ledger-integrity-org', 'TEST-C', 'Ledger integrity credit', TRUE, 'TEST', 1, '/', NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO journal_entries
                (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
            VALUES
                ('ledger-integrity-entry', 'ledger-integrity-org', 'ledger-integrity-period', '2026-01-10', 'Ledger immutability proof', 'POSTED', 'ledger-integrity-key', repeat('a', 64), NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO journal_entry_lines
                (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
            VALUES
                ('ledger-integrity-line', 'ledger-integrity-entry', 1, 'ledger-integrity-debit-account', 100.00, 0.00, NOW(), NOW())
            """
        )
        await connection.execute(
            """
            INSERT INTO ledger_postings
                (id, organization_id, fiscal_period_id, journal_entry_id, journal_entry_line_id, account_id, posting_date, line_number, debit, credit, created_at, updated_at)
            VALUES
                ('ledger-integrity-posting', 'ledger-integrity-org', 'ledger-integrity-period', 'ledger-integrity-entry', 'ledger-integrity-line', 'ledger-integrity-debit-account', '2026-01-10', 1, 100.00, 0.00, NOW(), NOW())
            """
        )

        with pytest.raises(asyncpg.PostgresError) as update_error:
            async with connection.transaction():
                await connection.execute(
                    "UPDATE ledger_postings SET description = 'tampered' WHERE id = 'ledger-integrity-posting'"
                )
        assert update_error.value.sqlstate == "55000"

        row = await connection.fetchrow(
            "SELECT description, debit, credit FROM ledger_postings WHERE id = 'ledger-integrity-posting'"
        )
        assert row["description"] is None
        assert row["debit"] == 100
        assert row["credit"] == 0

        with pytest.raises(asyncpg.PostgresError) as delete_error:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM ledger_postings WHERE id = 'ledger-integrity-posting'"
                )
        assert delete_error.value.sqlstate == "55000"

        remaining = await connection.fetchval(
            "SELECT COUNT(*) FROM ledger_postings WHERE id = 'ledger-integrity-posting'"
        )
        assert remaining == 1
    finally:
        await connection.execute(
            "DELETE FROM organizations WHERE id = 'ledger-integrity-org'"
        )
        await connection.close()
