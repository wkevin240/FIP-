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
                tc.constraint_name,
                kcu.column_name,
                ccu.table_schema AS referenced_schema,
                ccu.table_name AS referenced_table,
                ccu.column_name AS referenced_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_schema = kcu.constraint_schema
             AND tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON tc.constraint_schema = ccu.constraint_schema
             AND tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public'
              AND tc.table_name = 'customers'
              AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.constraint_name
            """
        )
        foreign_key_map = {
            row["constraint_name"]: (
                row["column_name"],
                row["referenced_schema"],
                row["referenced_table"],
                row["referenced_column"],
            )
            for row in foreign_keys
        }
        assert foreign_key_map == {
            "customers_created_by_fkey": ("created_by", "public", "users", "id"),
            "customers_organization_id_fkey": ("organization_id", "public", "organizations", "id"),
            "customers_updated_by_fkey": ("updated_by", "public", "users", "id"),
        }

        assert len(foreign_keys) == 3
    finally:
        await connection.close()
