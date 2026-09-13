"""Keep journal-entry lines attached to accounts in the same organization.

Revision ID: 20260913_0019
Revises: 20260912_0018
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260913_0019"
down_revision: Union[str, None] = "20260912_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_line_validate_account_tenant()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            journal_organization_id text;
            account_organization_id text;
        BEGIN
            SELECT organization_id
            INTO journal_organization_id
            FROM journal_entries
            WHERE id = NEW.journal_entry_id;

            IF journal_organization_id IS NULL THEN
                RAISE EXCEPTION 'journal entry line journal entry does not exist'
                    USING ERRCODE = '23503';
            END IF;

            SELECT organization_id
            INTO account_organization_id
            FROM accounts
            WHERE id = NEW.account_id;

            IF account_organization_id IS NULL THEN
                RAISE EXCEPTION 'journal entry line account does not exist'
                    USING ERRCODE = '23503';
            END IF;

            IF journal_organization_id <> account_organization_id THEN
                RAISE EXCEPTION 'journal entry line account must belong to the journal organization'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entry_lines_validate_account_tenant
        BEFORE INSERT OR UPDATE OF journal_entry_id, account_id
        ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_line_validate_account_tenant();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_entry_lines_validate_account_tenant ON journal_entry_lines"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS fip_journal_entry_line_validate_account_tenant()"
    )
