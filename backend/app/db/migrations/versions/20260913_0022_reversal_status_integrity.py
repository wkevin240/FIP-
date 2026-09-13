"""Require a posted reversal before a journal entry can be marked REVERSED.

Revision ID: 20260913_0022
Revises: 20260913_0021
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260913_0022"
down_revision: Union[str, None] = "20260913_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION = """
CREATE OR REPLACE FUNCTION enforce_journal_reversal_status_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.reversal_of_id IS NOT NULL
       AND NEW.reversal_of_id IS DISTINCT FROM OLD.reversal_of_id
       AND EXISTS (
            SELECT 1
            FROM journal_entries original
            WHERE original.organization_id = OLD.organization_id
              AND original.id = OLD.reversal_of_id
              AND original.status = 'REVERSED'
       ) THEN
        RAISE EXCEPTION
            'A REVERSED journal entry must retain its POSTED reversal reference'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM journal_entries original
        WHERE original.organization_id = NEW.organization_id
          AND original.reversal_of_id = NEW.id
          AND original.status = 'REVERSED'
    ) AND NEW.status <> 'POSTED' THEN
        RAISE EXCEPTION
            'A reversal referenced by a REVERSED journal entry must remain POSTED'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.status = 'REVERSED' AND NOT EXISTS (
        SELECT 1
        FROM journal_entries reversal
        WHERE reversal.organization_id = NEW.organization_id
          AND reversal.reversal_of_id = NEW.id
          AND reversal.status = 'POSTED'
    ) THEN
        RAISE EXCEPTION
            'A journal entry can be REVERSED only when a POSTED reversal exists'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.execute(_FUNCTION)
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_journal_reversal_status_integrity
        AFTER INSERT OR UPDATE OF organization_id, reversal_of_id, status
        ON journal_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_journal_reversal_status_integrity();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_reversal_status_integrity
        ON journal_entries;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_journal_reversal_status_integrity();")
