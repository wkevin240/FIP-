"""Protect posted journal entries and lines from direct mutation.

Revision ID: 20260912_0011
Revises: 20260912_0010
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0011"
down_revision: Union[str, None] = "20260912_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_protect_posted()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            current_status text;
        BEGIN
            SELECT status::text INTO current_status
            FROM journal_entries
            WHERE id = COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
            IF current_status IN ('POSTED', 'REVERSED') THEN
                RAISE EXCEPTION 'journal_entry_lines for posted/reversed entries are immutable; % is not permitted', TG_OP
                    USING ERRCODE = '55000';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entry_lines_no_posted_update
        BEFORE UPDATE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_protect_posted();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entry_lines_no_posted_delete
        BEFORE DELETE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_protect_posted();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_journal_entry_protect_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status::text IN ('POSTED', 'REVERSED') THEN
                RAISE EXCEPTION 'posted/reversed journal entries are immutable; DELETE is not permitted'
                    USING ERRCODE = '55000';
            END IF;
            RETURN OLD;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_no_posted_delete
        BEFORE DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION fip_journal_entry_protect_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_no_posted_delete ON journal_entries")
    op.execute("DROP FUNCTION IF EXISTS fip_journal_entry_protect_delete()")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entry_lines_no_posted_delete ON journal_entry_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entry_lines_no_posted_update ON journal_entry_lines")
    op.execute("DROP FUNCTION IF EXISTS fip_journal_entry_protect_posted()")
