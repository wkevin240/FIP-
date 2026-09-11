"""Enforce non-overlapping balance-sheet mapping ranges.

Revision ID: 20260911_0007
Revises: 20260911_0006
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260911_0007"
down_revision: Union[str, None] = "20260911_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # btree_gist supplies GiST equality operator classes for text columns so
    # PostgreSQL can enforce the tenant/account/version equality dimensions of
    # the exclusion constraint alongside the effective date range.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE balance_sheet_account_mappings
        ADD CONSTRAINT ex_balance_sheet_mapping_no_overlap
        EXCLUDE USING gist (
            organization_id WITH =,
            account_id WITH =,
            rule_version WITH =,
            daterange(effective_from, effective_to, '[]') WITH &&
        )
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ex_balance_sheet_mapping_no_overlap",
        "balance_sheet_account_mappings",
        type_="exclude",
    )
