"""Add tenant-scoped FP&A scenarios and explicit assumptions.
Revision ID: 0027_fpa_scenarios
Revises: 0026_fpa_analytical_dimensions
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_fpa_scenarios"
down_revision: str | None = "0026_fpa_analytical_dimensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    op.execute(f"GRANT {grants} ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "fpa_scenarios",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fiscal_year_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.UniqueConstraint("organization_id", "id", name="uq_fpa_scenario_org_id"),
        sa.UniqueConstraint("organization_id", "fiscal_year_id", "code", name="uq_fpa_scenario_org_year_code"),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'LOCKED')", name="ck_fpa_scenario_status"),
        sa.ForeignKeyConstraint(["organization_id", "fiscal_year_id"], ["fiscal_years.organization_id", "fiscal_years.id"], name="fk_fpa_scenario_org_year", ondelete="RESTRICT"),
    )
    _secure("fpa_scenarios")
    op.create_index("ix_fpa_scenarios_organization_id", "fpa_scenarios", ["organization_id"])
    op.create_index("ix_fpa_scenarios_fiscal_year_id", "fpa_scenarios", ["fiscal_year_id"])
    op.create_index("ix_fpa_scenarios_status", "fpa_scenarios", ["status"])

    op.create_table(
        "fpa_scenario_assumptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scenario_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("dimension_value_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_fpa_assumption_org_id"),
        sa.UniqueConstraint("organization_id", "scenario_id", "fiscal_period_id", "account_id", "dimension_value_id", name="uq_fpa_assumption_scope"),
        sa.CheckConstraint("amount <> 0", name="ck_fpa_assumption_non_zero"),
        sa.ForeignKeyConstraint(["organization_id", "scenario_id"], ["fpa_scenarios.organization_id", "fpa_scenarios.id"], name="fk_fpa_assumption_org_scenario", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "fiscal_period_id"], ["fiscal_periods.organization_id", "fiscal_periods.id"], name="fk_fpa_assumption_org_period", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "account_id"], ["accounts.organization_id", "accounts.id"], name="fk_fpa_assumption_org_account", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "dimension_value_id"], ["analytical_dimension_values.organization_id", "analytical_dimension_values.id"], name="fk_fpa_assumption_org_dimension_value", ondelete="RESTRICT"),
    )
    _secure("fpa_scenario_assumptions")
    op.create_index("ix_fpa_scenario_assumptions_organization_id", "fpa_scenario_assumptions", ["organization_id"])
    op.create_index("ix_fpa_scenario_assumptions_scenario_id", "fpa_scenario_assumptions", ["scenario_id"])
    op.create_index("ix_fpa_scenario_assumptions_fiscal_period_id", "fpa_scenario_assumptions", ["fiscal_period_id"])
    op.create_index("ix_fpa_scenario_assumptions_account_id", "fpa_scenario_assumptions", ["account_id"])
    op.create_index("ix_fpa_scenario_assumptions_dimension_value_id", "fpa_scenario_assumptions", ["dimension_value_id"])
    op.create_index("uq_fpa_assumption_scope_without_dimension", "fpa_scenario_assumptions", ["organization_id", "scenario_id", "fiscal_period_id", "account_id"], unique=True, postgresql_where=sa.text("dimension_value_id IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_fpa_assumption_scope_without_dimension", table_name="fpa_scenario_assumptions")
    op.drop_table("fpa_scenario_assumptions")
    op.drop_table("fpa_scenarios")
