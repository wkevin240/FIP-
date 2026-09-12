"""Keep journal entry dates inside their referenced fiscal period.

Revision ID: 20260912_0016
Revises: 20260912_0015
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0016"
down_revision: Union[str, None] = "20260912_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_validate_period_date()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            period_start date;
            period_end date;
        BEGIN
            SELECT start_date, end_date
            INTO period_start, period_end
            FROM fiscal_periods
            WHERE id = NEW.fiscal_period_id
              AND organization_id = NEW.organization_id;

            IF period_start IS NULL OR period_end IS NULL THEN
                RAISE EXCEPTION 'journal entry fiscal period does not exist for the organization'
                    USING ERRCODE = '23503';
            END IF;

            IF NEW.entry_date < period_start OR NEW.entry_date > period_end THEN
                RAISE EXCEPTION 'journal entry date must fall within its fiscal period'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_validate_period_date
        BEFORE INSERT OR UPDATE OF fiscal_period_id, organization_id, entry_date
        ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_validate_period_date();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_entries_validate_period_date ON journal_entries"
    )
    op.execute("DROP FUNCTION IF EXISTS fip_journal_entry_validate_period_date()")
