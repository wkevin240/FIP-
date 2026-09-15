import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_customer_postgres_constraints_are_deployed() -> None:
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
        table = await connection.fetchrow(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'customers'
            """
        )
        assert table is not None

        constraints = await connection.fetch(
            """
            SELECT conname, contype, convalidated, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'customers'::regclass
            ORDER BY conname
            """
        )
        definitions = {row["conname"]: row for row in constraints}

        assert definitions["uq_customer_organization_code"]["contype"] == "u"
        assert definitions["uq_customer_organization_tax_id"]["contype"] == "u"
        assert definitions["ck_customers_code_not_blank"]["contype"] == "c"
        assert definitions["ck_customers_code_no_whitespace"]["contype"] == "c"
        assert definitions["ck_customers_legal_name_not_blank"]["contype"] == "c"
        assert all(row["convalidated"] for row in definitions.values())

        foreign_keys = await connection.fetch(
            """
            SELECT confrelid::regclass::text AS referenced_table
            FROM pg_constraint
            WHERE conrelid = 'customers'::regclass
              AND contype = 'f'
            ORDER BY referenced_table
            """
        )
        assert {row["referenced_table"] for row in foreign_keys} == {"organizations", "users"}
    finally:
        await connection.close()
