"""Persist explicit balance-sheet account mappings.

Revision ID: 20260911_0006
Revises: 20260911_0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260911_0006"
down_revision: Union[str, None] = "20260911_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "balance_sheet_account_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "rule_version",
            "effective_from",
            name="uq_balance_sheet_mapping_scope_start",
        ),
        sa.CheckConstraint(
            "category IN ('ASSET', 'LIABILITY', 'EQUITY')",
            name="ck_balance_sheet_mapping_category",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_balance_sheet_mapping_effective_range",
        ),
    )
    op.create_index(
        "ix_balance_sheet_account_mappings_organization_id",
        "balance_sheet_account_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_balance_sheet_account_mappings_account_id",
        "balance_sheet_account_mappings",
        ["account_id"],
    )
    op.create_index(
        "ix_balance_sheet_account_mappings_rule_version",
        "balance_sheet_account_mappings",
        ["rule_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_balance_sheet_account_mappings_rule_version",
        table_name="balance_sheet_account_mappings",
    )
    op.drop_index(
        "ix_balance_sheet_account_mappings_account_id",
        table_name="balance_sheet_account_mappings",
    )
    op.drop_index(
        "ix_balance_sheet_account_mappings_organization_id",
        table_name="balance_sheet_account_mappings",
    )
    op.drop_table("balance_sheet_account_mappings")
