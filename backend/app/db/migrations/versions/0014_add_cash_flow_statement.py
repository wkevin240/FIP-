"""Add tenant-scoped cash-flow statement configuration.

Revision ID: 0014_cash_flow_statement
Revises: 0013_professional_reporting
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_cash_flow_statement"
down_revision: str | None = "0013_professional_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def upgrade() -> None:
    op.create_table(
        "cash_flow_account_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("is_cash_account", sa.Boolean(), nullable=False),
        sa.Column("cash_flow_category", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "(is_cash_account = true AND cash_flow_category IS NULL) "
            "OR (is_cash_account = false AND cash_flow_category "
            "IN ('OPERATING', 'INVESTING', 'FINANCING'))",
            name="ck_cash_flow_mapping_role",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_cash_flow_mapping_organization_account",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            name="uq_cash_flow_mapping_organization_account",
        ),
    )
    op.create_index(
        "ix_cash_flow_account_mappings_organization_id",
        "cash_flow_account_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_cash_flow_account_mappings_account_id",
        "cash_flow_account_mappings",
        ["account_id"],
    )
    op.execute(
        f"ALTER TABLE cash_flow_account_mappings OWNER TO {ACCOUNTING_OWNER_ROLE}"
    )
    op.execute("REVOKE ALL ON TABLE cash_flow_account_mappings FROM PUBLIC")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE cash_flow_account_mappings TO {APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cash_flow_account_mappings_account_id",
        table_name="cash_flow_account_mappings",
    )
    op.drop_index(
        "ix_cash_flow_account_mappings_organization_id",
        table_name="cash_flow_account_mappings",
    )
    op.drop_table("cash_flow_account_mappings")
