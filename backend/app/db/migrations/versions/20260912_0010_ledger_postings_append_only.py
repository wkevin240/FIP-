"""Protect immutable ledger postings from UPDATE and DELETE operations.

Revision ID: 20260912_0010
Revises: 20260911_0009
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0010"
down_revision: Union[str, None] = "20260911_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_ledger_postings_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'ledger_postings is immutable; % is not permitted', TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ledger_postings_no_update
        BEFORE UPDATE ON ledger_postings
        FOR EACH ROW
        EXECUTE FUNCTION fip_ledger_postings_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ledger_postings_no_delete
        BEFORE DELETE ON ledger_postings
        FOR EACH ROW
        EXECUTE FUNCTION fip_ledger_postings_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_postings_no_delete ON ledger_postings")
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_postings_no_update ON ledger_postings")
    op.execute("DROP FUNCTION IF EXISTS fip_ledger_postings_append_only()")
