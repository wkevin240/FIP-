"""Keep journal reversals inside their organization tenant.

Revision ID: 20260913_0021
Revises: 20260913_0020
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260913_0021"
down_revision: Union[str, None] = "20260913_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "journal_entries_reversal_of_id_fkey",
        "journal_entries",
        type_="foreignkey",
    )
    op.create_unique_constraint(
        "uq_journal_entry_organization_id",
        "journal_entries",
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_journal_entry_reversal_same_organization",
        "journal_entries",
        "journal_entries",
        ["organization_id", "reversal_of_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_journal_entry_reversal_same_organization",
        "journal_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_journal_entry_organization_id",
        "journal_entries",
        type_="unique",
    )
    op.create_foreign_key(
        "journal_entries_reversal_of_id_fkey",
        "journal_entries",
        "journal_entries",
        ["reversal_of_id"],
        ["id"],
        ondelete="RESTRICT",
    )
