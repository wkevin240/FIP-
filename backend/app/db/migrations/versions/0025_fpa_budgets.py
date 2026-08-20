"""Add tenant-scoped FP&A budgets and budget lines.

Revision ID: 0025_fpa_budgets
Revises: 0024_banking_control
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_fpa_budgets"
down_revision: str | None = "0024_banking_control"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, write: bool = True) -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    grants = "SELECT, INSERT, UPDATE" if write else "SELECT"
    op.execute(f"GRANT {grants} ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("fiscal_year_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_budget_organization_year",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_budgets_organization_id_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "name", name="uq_budget_organization_name"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'LOCKED')", name="ck_budget_status"
        ),
    )
    _secure("budgets")
    op.create_table(
        "budget_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("budget_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "budget_id"],
            ["budgets.organization_id", "budgets.id"],
            name="fk_budget_line_organization_budget",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "fiscal_period_id"],
            ["fiscal_periods.organization_id", "fiscal_periods.id"],
            name="fk_budget_line_organization_period",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_budget_line_organization_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "budget_id",
            "fiscal_period_id",
            "account_id",
            name="uq_budget_line_org_budget_period_account",
        ),
    )
    _secure("budget_lines")


def downgrade() -> None:
    op.drop_table("budget_lines")
    op.drop_table("budgets")
