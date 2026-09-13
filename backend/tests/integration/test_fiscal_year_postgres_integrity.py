"""Prove fiscal-year temporal integrity at the PostgreSQL boundary."""

import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_fiscal_years_cannot_overlap_within_organization() -> None:
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
            WHERE conrelid = 'fiscal_years'::regclass
              AND conname = 'ex_fiscal_year_organization_no_overlap'
            """
        )
        assert definition is not None
        assert "EXCLUDE USING gist" in definition
        assert "organization_id WITH =" in definition
        assert "daterange(start_date, end_date, '[]'::text) WITH &&" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES
                        ('fiscal-year-org', 'integration-only', TRUE, NOW(), NOW()),
                        ('fiscal-year-other', 'integration-only-other', TRUE, NOW(), NOW())
                    """
                )

                await connection.execute(
                    """
                    INSERT INTO fiscal_years
                        (id, organization_id, name, start_date, end_date, status)
                    VALUES
                        ('fiscal-year-base', 'fiscal-year-org', 'FY-2026', '2026-01-01', '2026-12-31', 'OPEN')
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as overlap_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO fiscal_years
                                (id, organization_id, name, start_date, end_date, status)
                            VALUES
                                ('fiscal-year-overlap', 'fiscal-year-org', 'FY-2026-OVERLAP', '2026-06-01', '2027-05-31', 'OPEN')
                            """
                        )
                assert overlap_error.value.sqlstate == "23P01"

                await connection.execute(
                    """
                    INSERT INTO fiscal_years
                        (id, organization_id, name, start_date, end_date, status)
                    VALUES
                        ('fiscal-year-next', 'fiscal-year-org', 'FY-2027', '2027-01-01', '2027-12-31', 'OPEN')
                    """
                )

                await connection.execute(
                    """
                    INSERT INTO fiscal_years
                        (id, organization_id, name, start_date, end_date, status)
                    VALUES
                        ('fiscal-year-other-org', 'fiscal-year-other', 'FY-2026', '2026-06-01', '2027-05-31', 'OPEN')
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as update_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            UPDATE fiscal_years
                            SET start_date = '2026-11-01'
                            WHERE id = 'fiscal-year-next'
                            """
                        )
                assert update_error.value.sqlstate == "23P01"

                row = await connection.fetchrow(
                    "SELECT start_date, end_date FROM fiscal_years WHERE id = 'fiscal-year-next'"
                )
                assert row is not None
                assert str(row["start_date"]) == "2027-01-01"
                assert str(row["end_date"]) == "2027-12-31"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
