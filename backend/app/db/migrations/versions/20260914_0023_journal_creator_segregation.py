"""Record journal creators and prevent self-posting.

Revision ID: 20260914_0023
Revises: 20260913_0022
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import Column, String


revision: str = "20260914_0023"
down_revision: Union[str, None] = "20260913_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION = """
CREATE OR REPLACE FUNCTION enforce_journal_creator_segregation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND NEW.created_by IS NULL THEN
        RAISE EXCEPTION
            'New journal entry must record its creator'
            USING ERRCODE = '23502';
    END IF;

    IF TG_OP = 'UPDATE'
       AND OLD.created_by IS DISTINCT FROM NEW.created_by THEN
        RAISE EXCEPTION
            'Journal entry creator is immutable after creation'
            USING ERRCODE = '42501';
    END IF;

    IF NEW.reversal_of_id IS NULL
       AND NEW.status IN ('POSTED', 'REVERSED')
       AND NEW.created_by IS NOT NULL
       AND NEW.posted_by IS NOT NULL
       AND NEW.created_by = NEW.posted_by THEN
        RAISE EXCEPTION
            'A journal entry creator cannot post or reverse the same entry'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.add_column("journal_entries", Column("created_by", String(), nullable=True))
    op.create_index(
        "ix_journal_entries_created_by",
        "journal_entries",
        ["created_by"],
        unique=False,
    )
    op.execute(_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER trg_journal_creator_segregation
        BEFORE INSERT OR UPDATE OF status, created_by, posted_by
        ON journal_entries
        FOR EACH ROW
        EXECUTE FUNCTION enforce_journal_creator_segregation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_journal_creator_segregation
        ON journal_entries;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_journal_creator_segregation();")
    op.drop_index("ix_journal_entries_created_by", table_name="journal_entries")
    op.drop_column("journal_entries", "created_by")
