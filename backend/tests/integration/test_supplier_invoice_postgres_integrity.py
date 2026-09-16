import os
import re

import psycopg2


def _connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_SERVER", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "fip_user"),
        password=os.getenv("POSTGRES_PASSWORD", "fip_password"),
        dbname=os.getenv("POSTGRES_DB", "fip_db"),
    )


def _normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def test_supplier_invoice_schema_constraints_are_deployed() -> None:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT conname, contype::text, convalidated
            FROM pg_constraint
            WHERE conrelid = to_regclass(format('%I.%I', current_schema(), 'supplier_invoices'))
            ORDER BY conname
            """
        )
        constraints = {name: (contype, validated) for name, contype, validated in cur.fetchall()}

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

        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'supplier_invoices'
            """
        )
        indexes = {name: definition for name, definition in cur.fetchall()}
        assert "ix_supplier_invoices_organization_status_date" in indexes
        assert "(organization_id, status, invoice_date)" in _normalize_sql(
            indexes["ix_supplier_invoices_organization_status_date"]
        )


def test_supplier_invoice_supplier_fk_is_tenant_scoped() -> None:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'fk_supplier_invoice_supplier_same_organization'
              AND conrelid = to_regclass(format('%I.%I', current_schema(), 'supplier_invoices'))
            """
        )
        row = cur.fetchone()
        assert row is not None
        definition = _normalize_sql(row[0])
        assert "foreign key (organization_id, supplier_id)" in definition
        assert "references suppliers(organization_id, id)" in definition
