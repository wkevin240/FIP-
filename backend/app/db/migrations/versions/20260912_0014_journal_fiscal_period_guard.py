"""Prevent journal mutations from bypassing fiscal-period closure.

Revision ID: 20260912_0014
Revises: 20260912_0013
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0014"
down_revision: Union[str, None] = "20260912_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_require_open_period()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            period_status text;
        BEGIN
            SELECT status::text
            INTO period_status
            FROM fiscal_periods
            WHERE id = NEW.fiscal_period_id
              AND organization_id = NEW.organization_id;

            IF period_status IS NULL THEN
                RAISE EXCEPTION 'journal entry fiscal period does not exist for the organization'
                    USING ERRCODE = '23503';
            END IF;

            IF period_status <> 'OPEN' THEN
                RAISE EXCEPTION 'journal entries can only be created or posted in an open fiscal period'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_require_open_period
        BEFORE INSERT OR UPDATE OF fiscal_period_id, organization_id, status ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_require_open_period();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_entries_require_open_period ON journal_entries"
    )
    op.execute("DROP FUNCTION IF EXISTS fip_journal_entry_require_open_period()")
