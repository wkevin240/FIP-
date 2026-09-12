"""Serialize journal-line mutations with journal posting transitions.

Revision ID: 20260912_0013
Revises: 20260912_0012
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0013"
down_revision: Union[str, None] = "20260912_0012"
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
            locked_status text;
            target_journal_id text;
        BEGIN
            target_journal_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);

            SELECT status::text
            INTO locked_status
            FROM journal_entries
            WHERE id = target_journal_id
            FOR UPDATE;

            IF locked_status IN ('POSTED', 'REVERSED') THEN
                RAISE EXCEPTION 'journal_entry_lines for posted/reversed entries are immutable; % is not permitted', TG_OP
                    USING ERRCODE = '55000';
            END IF;

            RETURN COALESCE(NEW, OLD);
        END;
        $$;
        """
    )


def downgrade() -> None:
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
