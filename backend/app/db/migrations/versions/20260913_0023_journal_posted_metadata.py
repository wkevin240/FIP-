"""Require audit metadata for posted journal entries.

Revision ID: 20260913_0023
Revises: 20260913_0022
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260913_0023"
down_revision: Union[str, None] = "20260913_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_journal_entry_posted_metadata",
        "journal_entries",
        "status = 'DRAFT' OR (posted_at IS NOT NULL AND posted_by IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_journal_entry_posted_metadata",
        "journal_entries",
        type_="check",
    )
