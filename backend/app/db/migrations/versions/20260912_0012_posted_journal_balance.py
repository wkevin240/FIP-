"""Enforce balanced journal lines before a journal can become immutable.

Revision ID: 20260912_0012
Revises: 20260912_0011
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0012"
down_revision: Union[str, None] = "20260912_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_require_balance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            total_debit numeric;
            total_credit numeric;
            line_count integer;
        BEGIN
            IF NEW.status::text IN ('POSTED', 'REVERSED') THEN
                SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                INTO line_count, total_debit, total_credit
                FROM journal_entry_lines
                WHERE journal_entry_id = NEW.id;

                IF line_count = 0 OR total_debit <> total_credit OR total_debit <= 0 THEN
                    RAISE EXCEPTION 'posted/reversed journal entries must contain balanced non-zero lines'
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
        CREATE TRIGGER trg_journal_entries_require_balance
        BEFORE INSERT OR UPDATE OF status ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_require_balance();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_require_balance ON journal_entries")
    op.execute("DROP FUNCTION IF EXISTS fip_journal_entry_require_balance()")
