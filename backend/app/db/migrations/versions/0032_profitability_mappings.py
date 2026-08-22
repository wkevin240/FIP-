"""Add explicit tenant-scoped profitability account mappings.

Revision ID: 0032_profitability_mappings
Revises: 0031_procurement_flow
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_profitability_mappings"
down_revision: str | None = "0031_procurement_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    op.execute(f"ALTER TABLE public.{name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE public.{name} FROM PUBLIC")
    op.execute(f"GRANT {grants} ON TABLE public.{name} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "profitability_account_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_profitability_mapping_org_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "category",
            name="uq_profitability_mapping_org_account_category",
        ),
        sa.CheckConstraint(
            "category IN ('REVENUE', 'COGS', 'OPERATING_EXPENSE', 'OTHER_INCOME', 'OTHER_EXPENSE')",
            name="ck_profitability_mapping_category",
        ),
    )
    _secure("profitability_account_mappings")
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


def downgrade() -> None:
    op.drop_index(
        "ix_profitability_account_mappings_account_id",
        table_name="profitability_account_mappings",
    )
    op.drop_index(
        "ix_profitability_account_mappings_organization_id",
        table_name="profitability_account_mappings",
    )
    op.drop_table("profitability_account_mappings")
