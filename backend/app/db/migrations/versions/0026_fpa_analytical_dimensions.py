"""Add tenant-scoped FP&A analytical dimensions and allocations.

Revision ID: 0026_fpa_analytical_dimensions
Revises: 0025_fpa_budgets
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_fpa_analytical_dimensions"
down_revision: str | None = "0025_fpa_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    op.execute(f"GRANT {grants} ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_journal_entry_lines_organization_id_id",
        "journal_entry_lines",
        ["organization_id", "id"],
    )
    op.create_table(
        "analytical_dimensions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.String(5), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_analytical_dimension_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_analytical_dimension_org_code"
        ),
    )
    _secure("analytical_dimensions")
    op.create_table(
        "analytical_dimension_values",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dimension_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_active", sa.String(5), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_analytical_value_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "dimension_id",
            "id",
            name="uq_analytical_value_org_dimension_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "dimension_id",
            "code",
            name="uq_analytical_value_org_dimension_code",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "dimension_id"],
            ["analytical_dimensions.organization_id", "analytical_dimensions.id"],
            name="fk_analytical_value_org_dimension",
            ondelete="RESTRICT",
        ),
    )
    _secure("analytical_dimension_values")
    op.create_table(
        "journal_entry_line_analytic_allocations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("journal_entry_line_id", sa.String(), nullable=False),
        sa.Column("dimension_id", sa.String(), nullable=False),
        sa.Column("dimension_value_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_analytic_allocation_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "journal_entry_line_id",
            "dimension_id",
            "dimension_value_id",
            name="uq_analytic_allocation_line_dimension_value",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_analytic_allocation_org_idempotency",
        ),
        sa.CheckConstraint("amount > 0", name="ck_analytic_allocation_positive_amount"),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_line_id"],
            ["journal_entry_lines.organization_id", "journal_entry_lines.id"],
            name="fk_analytic_allocation_org_line",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "dimension_id"],
            ["analytical_dimensions.organization_id", "analytical_dimensions.id"],
            name="fk_analytic_allocation_org_dimension",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "dimension_id", "dimension_value_id"],
            [
                "analytical_dimension_values.organization_id",
                "analytical_dimension_values.dimension_id",
                "analytical_dimension_values.id",
            ],
            name="fk_analytic_allocation_org_dimension_value",
            ondelete="RESTRICT",
        ),
    )
    _secure("journal_entry_line_analytic_allocations")
    op.drop_constraint(
        "uq_budget_line_org_budget_period_account",
        "budget_lines",
        type_="unique",
    )
    op.add_column(
        "budget_lines", sa.Column("dimension_value_id", sa.String(), nullable=True)
    )
    op.create_unique_constraint(
        "uq_budget_line_org_budget_period_account_dimension",
        "budget_lines",
        [
            "organization_id",
            "budget_id",
            "fiscal_period_id",
            "account_id",
            "dimension_value_id",
        ],
    )
    op.create_foreign_key(
        "fk_budget_line_organization_dimension_value",
        "budget_lines",
        "analytical_dimension_values",
        ["organization_id", "dimension_value_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_budget_lines_dimension_value_id", "budget_lines", ["dimension_value_id"]
    )
    op.create_index(
        "uq_budget_line_without_dimension",
        "budget_lines",
        ["organization_id", "budget_id", "fiscal_period_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("dimension_value_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_budget_line_without_dimension", table_name="budget_lines")
    op.drop_index("ix_budget_lines_dimension_value_id", table_name="budget_lines")
    op.drop_constraint(
        "uq_budget_line_org_budget_period_account_dimension",
        "budget_lines",
        type_="unique",
    )
    op.drop_constraint(
        "fk_budget_line_organization_dimension_value",
        "budget_lines",
        type_="foreignkey",
    )
    op.drop_column("budget_lines", "dimension_value_id")
    op.create_unique_constraint(
        "uq_budget_line_org_budget_period_account",
        "budget_lines",
        ["organization_id", "budget_id", "fiscal_period_id", "account_id"],
    )
    op.drop_table("journal_entry_line_analytic_allocations")
    op.drop_table("analytical_dimension_values")
    op.drop_table("analytical_dimensions")
    op.drop_constraint(
        "uq_journal_entry_lines_organization_id_id",
        "journal_entry_lines",
        type_="unique",
    )
