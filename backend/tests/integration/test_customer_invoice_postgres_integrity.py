import os

import asyncpg
import pytest


async def connect_postgres() -> asyncpg.Connection | None:
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
async def test_customer_invoice_schema_constraints_are_deployed():
    connection = await connect_postgres()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")
    try:
        table = await connection.fetchval(
            "SELECT to_regclass('public.customer_invoices')"
        )
        assert table == "customer_invoices"

        rows = await connection.fetch(
            """
            SELECT conname, contype::text AS contype, convalidated
            FROM pg_constraint
            WHERE conrelid = 'public.customer_invoices'::regclass
            """
        )
        constraints = {row["conname"]: row for row in rows}
        required = {
            "uq_customer_invoice_organization_number": "u",
            "uq_customer_invoices_organization_id_id": "u",
            "ck_customer_invoices_number_not_blank": "c",
            "ck_customer_invoices_currency_canonical": "c",
            "ck_customer_invoices_amounts_nonnegative": "c",
            "ck_customer_invoices_total_matches_components": "c",
            "ck_customer_invoices_due_date": "c",
            "ck_customer_invoices_issue_metadata": "c",
        }
        for name, kind in required.items():
            assert name in constraints, f"missing constraint: {name}"
            assert constraints[name]["contype"] == kind
            assert constraints[name]["convalidated"] is True

        status_default = await connection.fetchval(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'customer_invoices'
              AND column_name = 'status'
            """
        )
        assert status_default is not None
        assert "DRAFT" in status_default

        index = await connection.fetchval(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'customer_invoices'
              AND indexname = 'ix_customer_invoices_org_status_due_date'
            """
        )
        assert index is not None
        assert "(organization_id, status, due_date)" in index
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_customer_invoice_requires_customer_from_same_tenant():
    connection = await connect_postgres()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ($1, $2, TRUE)",
                "customer-invoice-fk-org-a", "customer-invoice-fk-org-a",
            )
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ($1, $2, TRUE)",
                "customer-invoice-fk-org-b", "customer-invoice-fk-org-b",
            )
            await connection.execute(
                """
                INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser)
                VALUES ($1, $2, $3, $4, TRUE, FALSE)
                """,
                "customer-invoice-fk-user", "customer-invoice-fk@example.invalid",
                "Invoice FK test", "not-a-real-password-hash",
            )
            await connection.execute(
                """
                INSERT INTO customers (
                    id, organization_id, code, legal_name, is_active, created_by, updated_by
                ) VALUES ($1, $2, $3, $4, TRUE, $5, $5)
                """,
                "customer-invoice-fk-customer", "customer-invoice-fk-org-b",
                "C-OTHER", "Other tenant customer", "customer-invoice-fk-user",
            )
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        """
                        INSERT INTO customer_invoices (
                            id, organization_id, customer_id, invoice_number,
                            invoice_date, due_date, currency_code,
                            subtotal, tax_amount, total_amount,
                            created_by, updated_by
                        ) VALUES (
                            $1, $2, $3, $4, DATE '2026-11-01', DATE '2026-11-30',
                            'XAF', 100.00, 19.25, 119.25, $5, $5
                        )
                        """,
                        "customer-invoice-fk-invoice", "customer-invoice-fk-org-a",
                        "customer-invoice-fk-customer", "INV-OTHER-TENANT",
                        "customer-invoice-fk-user",
                    )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_customer_invoice_database_defaults_to_draft():
    connection = await connect_postgres()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ($1, $2, TRUE)",
                "customer-invoice-default-org", "customer-invoice-default-org",
            )
            await connection.execute(
                """
                INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser)
                VALUES ($1, $2, $3, $4, TRUE, FALSE)
                """,
                "customer-invoice-default-user", "customer-invoice-default@example.invalid",
                "Invoice default test", "not-a-real-password-hash",
            )
            await connection.execute(
                """
                INSERT INTO customers (
                    id, organization_id, code, legal_name, is_active, created_by, updated_by
                ) VALUES ($1, $2, $3, $4, TRUE, $5, $5)
                """,
                "customer-invoice-default-customer", "customer-invoice-default-org",
                "C-DEFAULT", "Default test customer", "customer-invoice-default-user",
            )
            status_value = await connection.fetchval(
                """
                INSERT INTO customer_invoices (
                    id, organization_id, customer_id, invoice_number,
                    invoice_date, due_date, currency_code,
                    subtotal, tax_amount, total_amount, created_by, updated_by
                ) VALUES (
                    $1, $2, $3, $4, DATE '2026-11-01', DATE '2026-11-30',
                    'XAF', 100.00, 19.25, 119.25, $5, $5
                )
                RETURNING status
                """,
                "customer-invoice-default-invoice", "customer-invoice-default-org",
                "customer-invoice-default-customer", "INV-DEFAULT",
                "customer-invoice-default-user",
            )
            assert status_value == "DRAFT"
    finally:
        await connection.close()
