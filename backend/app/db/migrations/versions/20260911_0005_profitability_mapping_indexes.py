"""Add query indexes for tenant-scoped profitability mappings.

Revision ID: 20260911_0005
Revises: 20260910_0004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260911_0005"
down_revision: Union[str, None] = "20260910_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_profitability_account_mappings_organization_id",
        "profitability_account_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_profitability_account_mappings_account_id",
        "profitability_account_mappings",
        ["account_id"],
    )
    op.create_index(
        "ix_profitability_account_mappings_rule_version",
        "profitability_account_mappings",
        ["rule_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profitability_account_mappings_rule_version",
        table_name="profitability_account_mappings",
    )
    op.drop_index(
        "ix_profitability_account_mappings_account_id",
        table_name="profitability_account_mappings",
    )
    op.drop_index(
        "ix_profitability_account_mappings_organization_id",
        table_name="profitability_account_mappings",
    )
