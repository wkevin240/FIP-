import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_balance_sheet_mapping_overlap_constraint_exists_in_postgres() -> None:
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
        extension = await connection.fetchval(
            "SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'"
        )
        assert extension == 1

        constraint_metadata = await connection.fetchrow(
            """
            SELECT contype, convalidated, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'balance_sheet_account_mappings'::regclass
              AND conname = 'ex_balance_sheet_mapping_no_overlap'
              AND contype = 'x'
              AND convalidated
            """
        )

        assert constraint_metadata is not None

        constraint_definition = constraint_metadata["definition"]
        assert "EXCLUDE USING gist" in constraint_definition
        assert "organization_id WITH =" in constraint_definition
        assert "account_id WITH =" in constraint_definition
        assert "rule_version WITH =" in constraint_definition
        assert "effective_from" in constraint_definition
        assert "effective_to" in constraint_definition
        assert "&&" in constraint_definition
    finally:
        await connection.close()
