"""Keep account hierarchy references inside one organization.

Revision ID: 20260912_0018
Revises: 20260912_0017
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0018"
down_revision: Union[str, None] = "20260912_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_account_validate_hierarchy_tenant()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            parent_organization_id text;
            collective_organization_id text;
        BEGIN
            IF NEW.parent_id IS NOT NULL THEN
                IF NEW.parent_id = NEW.id THEN
                    RAISE EXCEPTION 'account cannot be its own parent'
                        USING ERRCODE = '23514';
                END IF;

                SELECT organization_id
                INTO parent_organization_id
                FROM accounts
                WHERE id = NEW.parent_id;

                IF parent_organization_id IS NULL THEN
                    RAISE EXCEPTION 'account parent does not exist'
                        USING ERRCODE = '23503';
                END IF;

                IF parent_organization_id <> NEW.organization_id THEN
                    RAISE EXCEPTION 'account parent must belong to the same organization'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            IF NEW.collective_account_id IS NOT NULL THEN
                IF NEW.collective_account_id = NEW.id THEN
                    RAISE EXCEPTION 'account cannot reference itself as collective account'
                        USING ERRCODE = '23514';
                END IF;

                SELECT organization_id
                INTO collective_organization_id
                FROM accounts
                WHERE id = NEW.collective_account_id;

                IF collective_organization_id IS NULL THEN
                    RAISE EXCEPTION 'collective account does not exist'
                        USING ERRCODE = '23503';
                END IF;

                IF collective_organization_id <> NEW.organization_id THEN
                    RAISE EXCEPTION 'collective account must belong to the same organization'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_accounts_validate_hierarchy_tenant
        BEFORE INSERT OR UPDATE OF organization_id, parent_id, collective_account_id
        ON accounts
        FOR EACH ROW EXECUTE FUNCTION fip_account_validate_hierarchy_tenant();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_accounts_validate_hierarchy_tenant ON accounts")
    op.execute("DROP FUNCTION IF EXISTS fip_account_validate_hierarchy_tenant()")
