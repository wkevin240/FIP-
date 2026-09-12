import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_ledger_postings_are_database_immutable() -> None:
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
        triggers = await connection.fetch(
            """
            SELECT tgname, pg_get_triggerdef(oid) AS definition
            FROM pg_trigger
            WHERE tgrelid = 'ledger_postings'::regclass
              AND NOT tgisinternal
            ORDER BY tgname
            """
        )
        definitions = {row["tgname"]: row["definition"] for row in triggers}

        assert "trg_ledger_postings_no_update" in definitions
        assert "trg_ledger_postings_no_delete" in definitions
        assert "BEFORE UPDATE" in definitions["trg_ledger_postings_no_update"]
        assert "BEFORE DELETE" in definitions["trg_ledger_postings_no_delete"]
        assert "fip_ledger_postings_append_only" in definitions["trg_ledger_postings_no_update"]
        assert "fip_ledger_postings_append_only" in definitions["trg_ledger_postings_no_delete"]
    finally:
        await connection.close()
