import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_fiscal_periods_cannot_overlap_or_escape_fiscal_year() -> None:
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
            WHERE tgrelid = 'fiscal_periods'::regclass
              AND tgname = 'trg_fiscal_period_validate'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF organization_id, fiscal_year_id, start_date, end_date" in definition
        assert "fip_fiscal_period_validate" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES ('period-integrity-org', 'period-integrity-org', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_years (id, name, start_date, end_date, organization_id, status, created_at, updated_at)
                    VALUES ('period-integrity-year', '2026', '2026-01-01', '2026-12-31', 'period-integrity-org', 'OPEN', NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO fiscal_periods (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                    VALUES ('period-integrity-base', 'January', '2026-01-01', '2026-01-31', 'OPEN', 'period-integrity-year', 'period-integrity-org', NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO fiscal_periods
                                (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                            VALUES
                                ('period-integrity-overlap', 'January overlap', '2026-01-15', '2026-02-15', 'OPEN', 'period-integrity-year', 'period-integrity-org', NOW(), NOW())
                            """
                        )
                assert error.value.sqlstate == "23514"

                with pytest.raises(asyncpg.PostgresError) as error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO fiscal_periods
                                (id, name, start_date, end_date, status, fiscal_year_id, organization_id, created_at, updated_at)
                            VALUES
                                ('period-integrity-outside', 'Outside year', '2025-12-01', '2026-01-31', 'OPEN', 'period-integrity-year', 'period-integrity-org', NOW(), NOW())
                            """
                        )
                assert error.value.sqlstate == "23514"

                count = await connection.fetchval(
                    "SELECT COUNT(*) FROM fiscal_periods WHERE organization_id = 'period-integrity-org'"
                )
                assert count == 1

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
