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
async def test_customer_postgres_constraints_are_deployed() -> None:
    connection = await _connect()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")

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
            "ck_customers_code_canonical": "c",
            "ck_customers_legal_name_not_blank": "c",
        }
        for name, constraint_type in required_constraints.items():
            assert name in definitions, f"missing PostgreSQL constraint: {name}"
            assert definitions[name]["contype"].decode() == constraint_type
            assert definitions[name]["convalidated"] is True

        foreign_keys = await connection.fetch(
            """
            SELECT
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
            """
        )
        foreign_key_map = {
            (
                row["column_name"],
                row["referenced_schema"],
                row["referenced_table"],
                row["referenced_column"],
            )
            for row in foreign_keys
        }
        assert foreign_key_map == {
            ("created_by", "public", "users", "id"),
            ("organization_id", "public", "organizations", "id"),
            ("updated_by", "public", "users", "id"),
        }
        assert len(foreign_keys) == 3
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_customer_postgres_active_lookup_index_is_deployed() -> None:
    connection = await _connect()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")

    try:
        index = await connection.fetchrow(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'customers'
              AND indexname = 'ix_customers_organization_active_code'
            """
        )
        assert index is not None
        assert '(organization_id, is_active, code)' in index["indexdef"]
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_customer_postgres_unique_constraints_reject_conflicting_rows() -> None:
    connection = await _connect()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")

    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ($1, $2, TRUE)",
                "customer-integrity-org",
                "customer-integrity-org",
            )
            await connection.execute(
                """
                INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser)
                VALUES ($1, $2, $3, $4, TRUE, FALSE)
                """,
                "customer-integrity-user",
                "customer-integrity@example.invalid",
                "Customer Integrity Test",
                "not-a-real-password-hash",
            )
            await connection.execute(
                """
                INSERT INTO customers (
                    id, organization_id, code, legal_name, tax_id,
                    is_active, created_by, updated_by
                )
                VALUES ($1, $2, $3, $4, $5, TRUE, $6, $6)
                """,
                "customer-integrity-1",
                "customer-integrity-org",
                "C-001",
                "Customer Integrity Test",
                "TAX-001",
                "customer-integrity-user",
            )

            async with connection.transaction():
                with pytest.raises(asyncpg.UniqueViolationError):
                    await connection.execute(
                        """
                        INSERT INTO customers (
                            id, organization_id, code, legal_name, tax_id,
                            is_active, created_by, updated_by
                        )
                        VALUES ($1, $2, $3, $4, $5, TRUE, $6, $6)
                        """,
                        "customer-integrity-2",
                        "customer-integrity-org",
                        "C-001",
                        "Second Customer",
                        "TAX-002",
                        "customer-integrity-user",
                    )

            async with connection.transaction():
                with pytest.raises(asyncpg.UniqueViolationError):
                    await connection.execute(
                        """
                        INSERT INTO customers (
                            id, organization_id, code, legal_name, tax_id,
                            is_active, created_by, updated_by
                        )
                        VALUES ($1, $2, $3, $4, $5, TRUE, $6, $6)
                        """,
                        "customer-integrity-3",
                        "customer-integrity-org",
                        "C-002",
                        "Third Customer",
                        "TAX-001",
                        "customer-integrity-user",
                    )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_customer_postgres_rejects_non_canonical_code() -> None:
    connection = await _connect()
    if connection is None:
        pytest.skip("PostgreSQL integration environment is not configured")

    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO organizations (id, name, is_active) VALUES ($1, $2, TRUE)",
                "customer-canonical-org",
                "customer-canonical-org",
            )
            await connection.execute(
                """
                INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser)
                VALUES ($1, $2, $3, $4, TRUE, FALSE)
                """,
                "customer-canonical-user",
                "customer-canonical@example.invalid",
                "Customer Canonical Test",
                "not-a-real-password-hash",
            )

            with pytest.raises(asyncpg.CheckViolationError):
                await connection.execute(
                    """
                    INSERT INTO customers (
                        id, organization_id, code, legal_name,
                        is_active, created_by, updated_by
                    )
                    VALUES ($1, $2, $3, $4, TRUE, $5, $5)
                    """,
                    "customer-canonical-1",
                    "customer-canonical-org",
                    "c-001",
                    "Customer Canonical Test",
                    "customer-canonical-user",
                )
    finally:
        await connection.close()
