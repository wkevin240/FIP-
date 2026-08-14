"""Add professional fixed asset management.

Revision ID: 0009_add_fixed_assets_management
Revises: 0008_add_payroll_management
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_fixed_assets_management"
down_revision: str | None = "0008_add_payroll_management"
branch_labels: str | None = None
depends_on: str | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "fixed_asset_accounting_profiles",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("profile_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("asset_account_id", sa.String(), nullable=False),
        sa.Column("accumulated_depreciation_account_id", sa.String(), nullable=False),
        sa.Column("depreciation_expense_account_id", sa.String(), nullable=False),
        sa.Column("acquisition_counterpart_account_id", sa.String(), nullable=False),
        sa.Column("disposal_proceeds_account_id", sa.String(), nullable=False),
        sa.Column("disposal_gain_account_id", sa.String(), nullable=False),
        sa.Column("disposal_loss_account_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["journal_id"], ["journals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["asset_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["accumulated_depreciation_account_id"],
            ["accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["depreciation_expense_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_counterpart_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["disposal_proceeds_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["disposal_gain_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["disposal_loss_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "profile_code",
            name="uq_fixed_asset_accounting_profile_code",
        ),
    )
    op.create_index(
        "ix_fixed_asset_accounting_profiles_organization_id",
        "fixed_asset_accounting_profiles",
        ["organization_id"],
    )
    op.create_index(
        "ix_fixed_asset_accounting_profiles_journal_id",
        "fixed_asset_accounting_profiles",
        ["journal_id"],
    )
    op.create_table(
        "fixed_asset_categories",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("accounting_profile_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_method", sa.String(32), nullable=False),
        sa.Column("default_useful_life_months", sa.Integer(), nullable=False),
        sa.Column("default_residual_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("default_declining_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "default_useful_life_months > 0",
            name="ck_fixed_asset_category_useful_life_positive",
        ),
        sa.CheckConstraint(
            "default_residual_rate >= 0 AND default_residual_rate <= 100",
            name="ck_fixed_asset_category_residual_rate",
        ),
        sa.CheckConstraint(
            "default_declining_rate IS NULL OR (default_declining_rate > 0 AND default_declining_rate <= 100)",
            name="ck_fixed_asset_category_declining_rate",
        ),
        sa.CheckConstraint(
            "default_method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_category_method",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["accounting_profile_id"],
            ["fixed_asset_accounting_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_fixed_asset_category_organization_code"
        ),
    )
    op.create_index(
        "ix_fixed_asset_categories_organization_id",
        "fixed_asset_categories",
        ["organization_id"],
    )
    op.create_index(
        "ix_fixed_asset_categories_accounting_profile_id",
        "fixed_asset_categories",
        ["accounting_profile_id"],
    )
    op.create_table(
        "fixed_assets",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("asset_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("serial_number", sa.String(128), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("available_for_use_date", sa.Date(), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("acquisition_journal_entry_id", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "acquisition_cost >= 0", name="ck_fixed_asset_cost_non_negative"
        ),
        sa.CheckConstraint(
            "residual_value >= 0 AND residual_value <= acquisition_cost",
            name="ck_fixed_asset_residual_value",
        ),
        sa.CheckConstraint(
            "available_for_use_date IS NULL OR available_for_use_date >= acquisition_date",
            name="ck_fixed_asset_available_date",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACQUIRED', 'IN_SERVICE', 'DISPOSED')",
            name="ck_fixed_asset_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["fixed_asset_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_journal_entry_id"],
            ["journal_entries.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "asset_code", name="uq_fixed_asset_organization_code"
        ),
        sa.UniqueConstraint("acquisition_journal_entry_id"),
    )
    for column in (
        "organization_id",
        "category_id",
        "acquisition_date",
        "available_for_use_date",
        "status",
    ):
        op.create_index(f"ix_fixed_assets_{column}", "fixed_assets", [column])
    op.create_table(
        "fixed_asset_components",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("component_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("declining_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "acquisition_cost >= 0", name="ck_fixed_asset_component_cost"
        ),
        sa.CheckConstraint(
            "residual_value >= 0 AND residual_value <= acquisition_cost",
            name="ck_fixed_asset_component_residual_value",
        ),
        sa.CheckConstraint(
            "useful_life_months > 0", name="ck_fixed_asset_component_useful_life"
        ),
        sa.CheckConstraint(
            "method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_component_method",
        ),
        sa.CheckConstraint(
            "declining_rate IS NULL OR (declining_rate > 0 AND declining_rate <= 100)",
            name="ck_fixed_asset_component_declining_rate",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name="ck_fixed_asset_component_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "asset_id", "component_code", name="uq_fixed_asset_component_code"
        ),
    )
    op.create_index(
        "ix_fixed_asset_components_organization_id",
        "fixed_asset_components",
        ["organization_id"],
    )
    op.create_index(
        "ix_fixed_asset_components_asset_id", "fixed_asset_components", ["asset_id"]
    )
    op.create_index(
        "ix_fixed_asset_components_status", "fixed_asset_components", ["status"]
    )
    op.create_table(
        "fixed_asset_depreciation_plans",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("component_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("declining_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("depreciable_base", sa.Numeric(18, 2), nullable=False),
        sa.Column("convention", sa.String(32), nullable=False),
        sa.Column("parameters_snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("activated_by_user_id", sa.String(), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_fixed_asset_plan_version"),
        sa.CheckConstraint(
            "useful_life_months > 0", name="ck_fixed_asset_plan_useful_life"
        ),
        sa.CheckConstraint(
            "depreciable_base >= 0", name="ck_fixed_asset_plan_depreciable_base"
        ),
        sa.CheckConstraint(
            "residual_value >= 0", name="ck_fixed_asset_plan_residual_value"
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_fixed_asset_plan_dates"),
        sa.CheckConstraint(
            "method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_plan_method",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'COMPLETED')",
            name="ck_fixed_asset_plan_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["component_id"], ["fixed_asset_components.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "component_id",
            "version_number",
            name="uq_fixed_asset_plan_component_version",
        ),
    )
    for column in (
        "organization_id",
        "asset_id",
        "component_id",
        "start_date",
        "end_date",
        "status",
    ):
        op.create_index(
            f"ix_fixed_asset_depreciation_plans_{column}",
            "fixed_asset_depreciation_plans",
            [column],
        )
    op.create_table(
        "fixed_asset_depreciation_schedule_lines",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("opening_net_book_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("depreciation_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 2), nullable=False),
        sa.Column("closing_net_book_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_user_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            "sequence_number > 0", name="ck_fixed_asset_schedule_sequence"
        ),
        sa.CheckConstraint(
            "depreciation_amount >= 0", name="ck_fixed_asset_schedule_amount"
        ),
        sa.CheckConstraint(
            "opening_net_book_value >= 0", name="ck_fixed_asset_schedule_opening_nbv"
        ),
        sa.CheckConstraint(
            "accumulated_depreciation >= 0", name="ck_fixed_asset_schedule_accumulated"
        ),
        sa.CheckConstraint(
            "closing_net_book_value >= 0", name="ck_fixed_asset_schedule_closing_nbv"
        ),
        sa.CheckConstraint(
            "status IN ('PLANNED', 'POSTED', 'VOIDED')",
            name="ck_fixed_asset_schedule_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["fixed_asset_depreciation_plans.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "plan_id", "sequence_number", name="uq_fixed_asset_schedule_plan_sequence"
        ),
        sa.UniqueConstraint(
            "journal_entry_id", name="uq_fixed_asset_schedule_journal_entry"
        ),
    )
    for column in (
        "organization_id",
        "plan_id",
        "fiscal_period_id",
        "scheduled_date",
        "status",
    ):
        op.create_index(
            f"ix_fixed_asset_depreciation_schedule_lines_{column}",
            "fixed_asset_depreciation_schedule_lines",
            [column],
        )
    op.create_table(
        "fixed_asset_disposals",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=False),
        sa.Column("disposal_type", sa.String(32), nullable=False),
        sa.Column("proceeds", sa.Numeric(18, 2), nullable=False),
        sa.Column("asset_cost", sa.Numeric(18, 2), nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_book_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("gain_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("loss_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_user_id", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("proceeds >= 0", name="ck_fixed_asset_disposal_proceeds"),
        sa.CheckConstraint(
            "asset_cost >= 0", name="ck_fixed_asset_disposal_asset_cost"
        ),
        sa.CheckConstraint(
            "accumulated_depreciation >= 0",
            name="ck_fixed_asset_disposal_accumulated_depreciation",
        ),
        sa.CheckConstraint(
            "net_book_value >= 0", name="ck_fixed_asset_disposal_net_book_value"
        ),
        sa.CheckConstraint("gain_amount >= 0", name="ck_fixed_asset_disposal_gain"),
        sa.CheckConstraint("loss_amount >= 0", name="ck_fixed_asset_disposal_loss"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'POSTED')", name="ck_fixed_asset_disposal_status"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("asset_id", name="uq_fixed_asset_disposal_asset"),
        sa.UniqueConstraint(
            "journal_entry_id", name="uq_fixed_asset_disposal_journal_entry"
        ),
    )
    for column in ("organization_id", "asset_id", "disposal_date", "status"):
        op.create_index(
            f"ix_fixed_asset_disposals_{column}", "fixed_asset_disposals", [column]
        )
    op.create_table(
        "fixed_asset_audit_events",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("context_ip", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("action <> ''", name="ck_fixed_asset_audit_event_action"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["fixed_assets.id"], ondelete="RESTRICT"),
    )
    for column in (
        "organization_id",
        "asset_id",
        "actor_user_id",
        "action",
        "resource_id",
        "occurred_at",
    ):
        op.create_index(
            f"ix_fixed_asset_audit_events_{column}",
            "fixed_asset_audit_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("fixed_asset_audit_events")
    op.drop_table("fixed_asset_disposals")
    op.drop_table("fixed_asset_depreciation_schedule_lines")
    op.drop_table("fixed_asset_depreciation_plans")
    op.drop_table("fixed_asset_components")
    op.drop_table("fixed_assets")
    op.drop_table("fixed_asset_categories")
    op.drop_table("fixed_asset_accounting_profiles")
