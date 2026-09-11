"""Prevent overlapping profitability mapping effective ranges.

Revision ID: 20260910_0004
Revises: 20260910_0003
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260910_0004"
down_revision: Union[str, None] = "20260910_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The exclusion constraint makes the temporal invariant race-safe at the
    # database boundary. btree_gist supplies GiST equality operators for the
    # text scope columns used alongside the daterange overlap operator.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE profitability_account_mappings
        ADD CONSTRAINT ex_profitability_mapping_no_overlap
        EXCLUDE USING gist (
            organization_id WITH =,
            account_id WITH =,
            rule_version WITH =,
            daterange(
                effective_from,
                CASE
                    WHEN effective_to IS NULL THEN NULL
                    ELSE effective_to + 1
                END,
                '[]'
            ) WITH &&
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE profitability_account_mappings "
        "DROP CONSTRAINT IF EXISTS ex_profitability_mapping_no_overlap"
    )
