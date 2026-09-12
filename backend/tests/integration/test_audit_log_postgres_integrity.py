import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_audit_log_schema_is_tenant_scoped_and_append_ordered() -> None:
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
        columns = await connection.fetch(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'audit_logs'
            ORDER BY ordinal_position
            """
        )
        column_names = [row["column_name"] for row in columns]
        assert "organization_id" in column_names
        assert "sequence_no" in column_names
        assert "previous_hash" in column_names
        assert "record_hash" in column_names
        assert "payload_json" in column_names

        constraints = await connection.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'audit_logs'::regclass
            """
        )
        names = {row["conname"] for row in constraints}
        assert "uq_audit_log_organization_sequence" in names
        assert "uq_audit_log_organization_hash" in names
        assert "ck_audit_log_sequence_positive" in names

        triggers = await connection.fetch(
            """
            SELECT tgname, pg_get_triggerdef(oid) AS definition
            FROM pg_trigger
            WHERE tgrelid = 'audit_logs'::regclass
              AND NOT tgisinternal
            ORDER BY tgname
            """
        )
        trigger_definitions = {row["tgname"]: row["definition"] for row in triggers}
        assert "trg_audit_logs_no_update" in trigger_definitions
        assert "trg_audit_logs_no_delete" in trigger_definitions
        assert "BEFORE UPDATE" in trigger_definitions["trg_audit_logs_no_update"]
        assert "BEFORE DELETE" in trigger_definitions["trg_audit_logs_no_delete"]
        assert "fip_audit_logs_append_only" in trigger_definitions["trg_audit_logs_no_update"]
        assert "fip_audit_logs_append_only" in trigger_definitions["trg_audit_logs_no_delete"]
    finally:
        await connection.close()
