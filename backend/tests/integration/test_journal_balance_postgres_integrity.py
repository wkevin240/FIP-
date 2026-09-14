import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_posted_journal_entries_require_balanced_lines() -> None:
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
              AND tgname = 'trg_journal_entries_require_balance'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF status" in definition
        assert "fip_journal_entry_require_balance" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('journal-balance-org', 'journal-balance-org', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('journal-balance-year', '2026', '2026-01-01', '2026-12-31', 'journal-balance-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('journal-balance-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'journal-balance-year', 'journal-balance-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES
                        ('journal-balance-debit', 'journal-balance-org', 'TEST-D', 'Debit test account', TRUE, 'TEST', 1, '/', NOW(), NOW()),
                        ('journal-balance-credit', 'journal-balance-org', 'TEST-C', 'Credit test account', TRUE, 'TEST', 1, '/', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_by, created_at, updated_at)
                    VALUES
                        ('journal-balance-unbalanced', 'journal-balance-org', 'journal-balance-period', '2026-01-10', 'Unbalanced transition proof', 'DRAFT', 'journal-balance-unbalanced-key', repeat('a', 64), 'journal-balance-test-creator', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('journal-balance-unbalanced-line', 'journal-balance-unbalanced', 1, 'journal-balance-debit', 100.00, 0.00, NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            "UPDATE journal_entries SET status = 'POSTED' WHERE id = 'journal-balance-unbalanced'"
                        )
                assert error.value.sqlstate == "23514"

                status = await connection.fetchval(
                    "SELECT status::text FROM journal_entries WHERE id = 'journal-balance-unbalanced'"
                )
                assert status == "DRAFT"

                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_by, created_at, updated_at)
                    VALUES
                        ('journal-balance-balanced', 'journal-balance-org', 'journal-balance-period', '2026-01-10', 'Balanced transition proof', 'DRAFT', 'journal-balance-balanced-key', repeat('b', 64), 'journal-balance-test-creator', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('journal-balance-balanced-debit', 'journal-balance-balanced', 1, 'journal-balance-debit', 100.00, 0.00, NOW(), NOW()),
                        ('journal-balance-balanced-credit', 'journal-balance-balanced', 2, 'journal-balance-credit', 0.00, 100.00, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    UPDATE journal_entries
                    SET status = 'POSTED',
                        posted_at = TIMESTAMPTZ '2026-01-10 12:00:00+00',
                        posted_by = 'journal-balance-test-actor'
                    WHERE id = 'journal-balance-balanced'
                    """
                )
                row = await connection.fetchrow(
                    "SELECT status::text AS status, posted_at, posted_by FROM journal_entries WHERE id = 'journal-balance-balanced'"
                )
                assert row["status"] == "POSTED"
                assert row["posted_at"] is not None
                assert row["posted_by"] == "journal-balance-test-actor"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
