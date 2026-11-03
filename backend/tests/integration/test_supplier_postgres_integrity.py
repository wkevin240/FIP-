import os

import asyncpg
import pytest


async def _connect() -> asyncpg.Connection | None:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        return None
    return await asyncpg.connect(
        host=server,
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "fip_user"),
        password=os.getenv("POSTGRES_PASSWORD", "fip_password"),
        database=os.getenv("POSTGRES_DB", "fip_db"),
    )


@pytest.mark.asyncio
async def test_supplier_postgres_constraints_and_index_are_deployed() -> None:
    connection = await _connect()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")
    try:
        table = await connection.fetchrow(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'suppliers'
            """
        )
        assert table is not None

        constraints = await connection.fetch(
            """
            SELECT conname, contype::text AS contype, convalidated
            FROM pg_constraint
            WHERE conrelid = 'public.suppliers'::regclass
            """
        )
        definitions = {row["conname"]: row for row in constraints}
        required = {
            "uq_supplier_organization_code": "u",
            "uq_supplier_organization_tax_id": "u",
            "ck_suppliers_code_not_blank": "c",
            "ck_suppliers_code_no_whitespace": "c",
            "ck_suppliers_code_canonical": "c",
            "ck_suppliers_legal_name_not_blank": "c",
        }
        for name, constraint_type in required.items():
            assert name in definitions, f"missing PostgreSQL constraint: {name}"
            assert definitions[name]["contype"] == constraint_type
            assert definitions[name]["convalidated"] is True

        foreign_keys = await connection.fetch(
            """
            SELECT kcu.column_name, ccu.table_name AS referenced_table, ccu.column_name AS referenced_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_schema = kcu.constraint_schema
             AND tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON tc.constraint_schema = ccu.constraint_schema
             AND tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public' AND tc.table_name = 'suppliers'
              AND tc.constraint_type = 'FOREIGN KEY'
            """
        )
        assert {
            (row["column_name"], row["referenced_table"], row["referenced_column"])
            for row in foreign_keys
        } == {
            ("created_by", "users", "id"),
            ("organization_id", "organizations", "id"),
            ("updated_by", "users", "id"),
        }

        index = await connection.fetchrow(
            """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = 'suppliers'
              AND indexname = 'ix_suppliers_organization_active_code'
            """
        )
        assert index is not None
        assert '(organization_id, is_active, code)' in index["indexdef"]
    finally:
        await connection.close()
