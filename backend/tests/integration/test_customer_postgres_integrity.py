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
            SELECT conname, contype, convalidated
            FROM pg_constraint
            WHERE conrelid = 'public.customers'::regclass
            """
        )
        definitions = {row["conname"]: row for row in constraints}

        required_constraints = {
            "uq_customer_organization_code": "u",
            "uq_customer_organization_tax_id": "u",
            "ck_customers_code_not_blank": "c",
            "ck_customers_code_no_whitespace": "c",
            "ck_customers_legal_name_not_blank": "c",
        }
        for name, constraint_type in required_constraints.items():
            assert name in definitions
            assert definitions[name]["contype"] == constraint_type
            assert definitions[name]["convalidated"] is True

        foreign_keys = await connection.fetch(
            """
            SELECT
                conname,
                confrelid::regclass::text AS referenced_table,
                convalidated
            FROM pg_constraint
            WHERE conrelid = 'public.customers'::regclass
              AND contype = 'f'
            """
        )
        foreign_key_targets = {row["referenced_table"] for row in foreign_keys}
        assert foreign_key_targets == {"organizations", "users"}
        assert len(foreign_keys) == 3
        assert all(row["convalidated"] is True for row in foreign_keys)
    finally:
        await connection.close()
