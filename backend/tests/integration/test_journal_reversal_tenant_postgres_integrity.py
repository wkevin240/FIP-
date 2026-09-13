import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_journal_reversal_cannot_cross_organization_boundary() -> None:
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
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'journal_entries'::regclass
              AND conname = 'fk_journal_entry_reversal_same_organization'
            """
        )
        assert definition is not None
        assert "FOREIGN KEY (organization_id, reversal_of_id)" in definition
        assert "REFERENCES journal_entries(organization_id, id)" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('reversal-org-a', 'integration-only-a', TRUE, NOW(), NOW()),
                           ('reversal-org-b', 'integration-only-b', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('reversal-year-a', '2026', '2026-01-01', '2026-12-31', 'reversal-org-a', 'OPEN', NOW(), NOW()),
                           ('reversal-year-b', '2026', '2026-01-01', '2026-12-31', 'reversal-org-b', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('reversal-period-a', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'reversal-year-a', 'reversal-org-a', NOW(), NOW()),
                           ('reversal-period-b', 'January 2026', '2026-01-01', '2026-01-31', 'OPEN', 'reversal-year-b', 'reversal-org-b', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, created_at, updated_at)
                    VALUES
                        ('reversal-original', 'reversal-org-a', 'reversal-period-a', '2026-01-10', 'integration-only', 'POSTED', 'reversal-original-key', repeat('a', 64), NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO journal_entries
                                (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, reversal_of_id, created_at, updated_at)
                            VALUES
                                ('reversal-cross-tenant', 'reversal-org-b', 'reversal-period-b', '2026-01-10', 'integration-only', 'POSTED', 'reversal-cross-tenant-key', repeat('b', 64), 'reversal-original', NOW(), NOW())
                            """
                        )
                assert error.value.sqlstate == "23503"

                await connection.execute(
                    """
                    INSERT INTO journal_entries
                        (id, organization_id, fiscal_period_id, entry_date, description, status, idempotency_key, idempotency_hash, reversal_of_id, created_at, updated_at)
                    VALUES
                        ('reversal-same-tenant', 'reversal-org-a', 'reversal-period-a', '2026-01-10', 'integration-only', 'POSTED', 'reversal-same-tenant-key', repeat('c', 64), 'reversal-original', NOW(), NOW())
                    """
                )

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
