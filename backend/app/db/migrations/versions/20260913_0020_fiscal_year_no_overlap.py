"""Prevent overlapping fiscal years within an organization.

Revision ID: 20260913_0020
Revises: 20260913_0019
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260913_0020"
down_revision: Union[str, None] = "20260913_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE fiscal_years
        ADD CONSTRAINT ex_fiscal_year_organization_no_overlap
        EXCLUDE USING gist (
            organization_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE fiscal_years
        DROP CONSTRAINT IF EXISTS ex_fiscal_year_organization_no_overlap
        """
    )
