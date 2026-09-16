import os
import re

import asyncpg
import pytest


async def _connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_SERVER", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "fip_user"),
        password=os.getenv("POSTGRES_PASSWORD", "fip_password"),
        database=os.getenv("POSTGRES_DB", "fip_db"),
    )


def _normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


async def _supplier_invoice_oid(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow(
        """
        SELECT c.oid
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname = 'supplier_invoices'
          AND c.relkind IN ('r', 'p')
        """
    )
    assert row is not None, "supplier_invoices table is not deployed in the current schema"
    return row["oid"]


@pytest.mark.asyncio
async def test_supplier_invoice_schema_constraints_are_deployed() -> None:
    conn = await _connection()
    try:
        relation_oid = await _supplier_invoice_oid(conn)
        rows = await conn.fetch(
            """
            SELECT conname, contype::text AS contype, convalidated
            FROM pg_constraint
            WHERE conrelid = $1
            ORDER BY conname
            """,
            relation_oid,
        )
        constraints = {
            row["conname"]: (row["contype"], row["convalidated"])
            for row in rows
        }

        expected_checks = {
            "ck_supplier_invoice_number_not_blank",
            "ck_supplier_invoice_due_on_or_after_invoice",
            "ck_supplier_invoice_amounts_non_negative",
            "ck_supplier_invoice_total_matches_components",
        }
        for name in expected_checks:
            assert constraints[name] == ("c", True)

        assert constraints["uq_supplier_invoice_org_supplier_number"] == ("u", True)
        assert constraints["fk_supplier_invoice_supplier_same_organization"] == ("f", True)

        index_rows = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'supplier_invoices'
            """
        )
        indexes = {row["indexname"]: row["indexdef"] for row in index_rows}
        assert "ix_supplier_invoices_organization_status_date" in indexes
        assert "(organization_id, status, invoice_date)" in _normalize_sql(
            indexes["ix_supplier_invoices_organization_status_date"]
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_supplier_invoice_supplier_fk_is_tenant_scoped() -> None:
    conn = await _connection()
    try:
        relation_oid = await _supplier_invoice_oid(conn)
        row = await conn.fetchrow(
            """
            SELECT pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conname = 'fk_supplier_invoice_supplier_same_organization'
              AND conrelid = $1
            """,
            relation_oid,
        )
        assert row is not None
        definition = _normalize_sql(row["definition"])
        assert "foreign key (organization_id, supplier_id)" in definition
        assert "references suppliers(organization_id, id)" in definition
    finally:
        await conn.close()
