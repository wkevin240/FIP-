import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_posted_journal_requires_posting_metadata() -> None:
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
        constraint = await connection.fetchval(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'journal_entries'::regclass
              AND conname = 'ck_journal_entry_posted_metadata'
            """
        )
        assert constraint is not None
        assert "status" in constraint
        assert "posted_at IS NOT NULL" in constraint
        assert "posted_by IS NOT NULL" in constraint

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('posted-metadata-org', 'integration-only', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('posted-metadata-year', '2026', '2026-01-01', '2026-12-31', 'posted-metadata-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('posted-metadata-period', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'posted-metadata-year', 'posted-metadata-org', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES ('posted-metadata-account', 'posted-metadata-org', 'TEST-META', 'Integration account', TRUE, 'TEST', 1, '/', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                    VALUES
                        ('posted-metadata-entry', 'posted-metadata-org', 'posted-metadata-period', '2026-01-10', 'integration-only', 'DRAFT', 'posted-metadata-key', repeat('a', 64), NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entry_lines
                        (id, journal_entry_id, line_number, account_id, debit, credit, created_at, updated_at)
                    VALUES
                        ('posted-metadata-debit', 'posted-metadata-entry', 1, 'posted-metadata-account', 100.00, 0.00, NOW(), NOW()),
                        ('posted-metadata-credit', 'posted-metadata-entry', 2, 'posted-metadata-account', 0.00, 100.00, NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as violation:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            UPDATE journal_entries
                            SET status = 'POSTED'
                            WHERE id = 'posted-metadata-entry'
                            """
                        )
                assert violation.value.sqlstate == "23514"

                status = await connection.fetchval(
                    "SELECT status::text FROM journal_entries WHERE id = 'posted-metadata-entry'"
                )
                assert status == "DRAFT"

                await connection.execute(
                    """
                    UPDATE journal_entries
                    SET status = 'POSTED', posted_at = NOW(), posted_by = 'integration-actor'
                    WHERE id = 'posted-metadata-entry'
                    """
                )
                row = await connection.fetchrow(
                    "SELECT status::text AS status, posted_at, posted_by FROM journal_entries WHERE id = 'posted-metadata-entry'"
                )
                assert row["status"] == "POSTED"
                assert row["posted_at"] is not None
                assert row["posted_by"] == "integration-actor"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
