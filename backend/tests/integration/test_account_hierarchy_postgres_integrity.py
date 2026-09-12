import os

import asyncpg
import pytest


class _RollbackFixture(Exception):
    pass


@pytest.mark.asyncio
async def test_account_hierarchy_references_stay_within_organization() -> None:
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
        definition = await connection.fetchval(
            """
            SELECT pg_get_triggerdef(oid)
            FROM pg_trigger
            WHERE tgrelid = 'accounts'::regclass
              AND tgname = 'trg_accounts_validate_hierarchy_tenant'
              AND NOT tgisinternal
            """
        )
        assert definition is not None
        assert "BEFORE" in definition
        assert "INSERT OR UPDATE OF organization_id, parent_id, collective_account_id" in definition
        assert "fip_account_validate_hierarchy_tenant" in definition

        try:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO organizations (id, name, is_active, created_at, updated_at)
                    VALUES
                        ('account-hierarchy-org', 'integration-only', TRUE, NOW(), NOW()),
                        ('account-hierarchy-other', 'integration-only-other', TRUE, NOW(), NOW())
                    """
                )
                await connection.execute(
                    """
                    INSERT INTO accounts
                        (id, organization_id, code, name, is_active, account_type, level, path, created_at, updated_at)
                    VALUES
                        ('account-hierarchy-parent', 'account-hierarchy-org', 'PARENT', 'integration-only', TRUE, 'TEST', 1, '/PARENT/', NOW(), NOW()),
                        ('account-hierarchy-collective', 'account-hierarchy-org', 'COLLECTIVE', 'integration-only', TRUE, 'TEST', 1, '/COLLECTIVE/', NOW(), NOW()),
                        ('account-hierarchy-other-parent', 'account-hierarchy-other', 'OTHER', 'integration-only', TRUE, 'TEST', 1, '/OTHER/', NOW(), NOW())
                    """
                )

                with pytest.raises(asyncpg.PostgresError) as parent_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO accounts
                                (id, organization_id, code, name, is_active, account_type, level, path, parent_id, created_at, updated_at)
                            VALUES
                                ('account-hierarchy-cross-parent', 'account-hierarchy-org', 'CHILD-P', 'integration-only', TRUE, 'TEST', 2, '/PARENT/CHILD-P/', 'account-hierarchy-other-parent', NOW(), NOW())
                            """
                        )
                assert parent_error.value.sqlstate == "23514"

                with pytest.raises(asyncpg.PostgresError) as collective_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO accounts
                                (id, organization_id, code, name, is_active, account_type, level, path, collective_account_id, created_at, updated_at)
                            VALUES
                                ('account-hierarchy-cross-collective', 'account-hierarchy-org', 'CHILD-C', 'integration-only', TRUE, 'TEST', 1, '/CHILD-C/', 'account-hierarchy-other-parent', NOW(), NOW())
                            """
                        )
                assert collective_error.value.sqlstate == "23514"

                with pytest.raises(asyncpg.PostgresError) as self_parent_error:
                    async with connection.transaction():
                        await connection.execute(
                            """
                            INSERT INTO accounts
                                (id, organization_id, code, name, is_active, account_type, level, path, parent_id, created_at, updated_at)
                            VALUES
                                ('account-hierarchy-self', 'account-hierarchy-org', 'SELF', 'integration-only', TRUE, 'TEST', 1, '/SELF/', 'account-hierarchy-self', NOW(), NOW())
                            """
                        )
                assert self_parent_error.value.sqlstate == "23514"

                await connection.execute(
                    """
                    INSERT INTO accounts
                        (id, organization_id, code, name, is_active, account_type, level, path, parent_id, collective_account_id, created_at, updated_at)
                    VALUES
                        ('account-hierarchy-valid', 'account-hierarchy-org', 'VALID', 'integration-only', TRUE, 'TEST', 2, '/PARENT/VALID/', 'account-hierarchy-parent', 'account-hierarchy-collective', NOW(), NOW())
                    """
                )
                row = await connection.fetchrow(
                    "SELECT organization_id, parent_id, collective_account_id FROM accounts WHERE id = 'account-hierarchy-valid'"
                )
                assert row is not None
                assert row["organization_id"] == "account-hierarchy-org"
                assert row["parent_id"] == "account-hierarchy-parent"
                assert row["collective_account_id"] == "account-hierarchy-collective"

                raise _RollbackFixture
        except _RollbackFixture:
            pass
    finally:
        await connection.close()
