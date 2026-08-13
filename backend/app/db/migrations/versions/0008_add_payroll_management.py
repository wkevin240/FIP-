"""Add professional payroll management.

Revision ID: 0008_add_payroll_management
Revises: 0007_add_treasury_bank_accounts
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_payroll_management"
down_revision: str | None = "0007_add_treasury_bank_accounts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "payroll_employees",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("employee_code", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("tax_identifier", sa.String(length=64), nullable=True),
        sa.Column("social_security_number", sa.String(length=64), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_payroll_employee_organization_code",
        ),
    )
    op.create_index(
        "ix_payroll_employees_organization_id",
        "payroll_employees",
        ["organization_id"],
    )

    op.create_table(
        "payroll_contracts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("contract_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("base_salary", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "base_salary >= 0", name="ck_payroll_contract_base_salary_non_negative"
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_payroll_contract_dates",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED')",
            name="ck_payroll_contract_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["payroll_employees.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "contract_number",
            name="uq_payroll_contract_organization_number",
        ),
    )
    op.create_index(
        "ix_payroll_contracts_employee_id", "payroll_contracts", ["employee_id"]
    )
    op.create_index(
        "ix_payroll_contracts_organization_id", "payroll_contracts", ["organization_id"]
    )
    op.create_index(
        "ix_payroll_contracts_start_date", "payroll_contracts", ["start_date"]
    )
    op.create_index("ix_payroll_contracts_end_date", "payroll_contracts", ["end_date"])
    op.create_index("ix_payroll_contracts_status", "payroll_contracts", ["status"])

    op.create_table(
        "payroll_rule_sets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "professional_expense_rate",
            sa.Numeric(precision=9, scale=6),
            nullable=False,
        ),
        sa.Column(
            "professional_expense_cap", sa.Numeric(precision=18, scale=2), nullable=True
        ),
        sa.Column(
            "annual_tax_allowance", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column(
            "local_surtax_rate", sa.Numeric(precision=9, scale=6), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_payroll_rule_set_dates",
        ),
        sa.CheckConstraint(
            "professional_expense_rate >= 0 AND professional_expense_rate <= 100",
            name="ck_payroll_rule_set_expense_rate",
        ),
        sa.CheckConstraint(
            "local_surtax_rate >= 0 AND local_surtax_rate <= 100",
            name="ck_payroll_rule_set_surtax_rate",
        ),
        sa.CheckConstraint(
            "professional_expense_cap IS NULL OR professional_expense_cap >= 0",
            name="ck_payroll_rule_set_expense_cap",
        ),
        sa.CheckConstraint(
            "annual_tax_allowance >= 0", name="ck_payroll_rule_set_allowance"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "code",
            "effective_from",
            name="uq_payroll_rule_set_organization_code_effective",
        ),
    )
    op.create_index(
        "ix_payroll_rule_sets_organization_id", "payroll_rule_sets", ["organization_id"]
    )
    op.create_index(
        "ix_payroll_rule_sets_effective_from", "payroll_rule_sets", ["effective_from"]
    )
    op.create_index(
        "ix_payroll_rule_sets_effective_to", "payroll_rule_sets", ["effective_to"]
    )

    op.create_table(
        "payroll_contribution_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("rule_set_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("base_type", sa.String(length=32), nullable=False),
        sa.Column("rate", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("cap_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "rate >= 0", name="ck_payroll_contribution_rate_non_negative"
        ),
        sa.CheckConstraint("rate <= 100", name="ck_payroll_contribution_rate_maximum"),
        sa.CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="ck_payroll_contribution_cap_non_negative",
        ),
        sa.CheckConstraint(
            "direction IN ('EMPLOYEE', 'EMPLOYER')",
            name="ck_payroll_contribution_direction",
        ),
        sa.CheckConstraint(
            "base_type IN ('GROSS', 'TAXABLE_GROSS')",
            name="ck_payroll_contribution_base_type",
        ),
        sa.CheckConstraint(
            "sort_order > 0", name="ck_payroll_contribution_sort_order_positive"
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id"], ["payroll_rule_sets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_set_id", "code", name="uq_payroll_contribution_rule_set_code"
        ),
    )
    op.create_index(
        "ix_payroll_contribution_rules_rule_set_id",
        "payroll_contribution_rules",
        ["rule_set_id"],
    )

    op.create_table(
        "payroll_tax_brackets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("rule_set_id", sa.String(), nullable=False),
        sa.Column("lower_bound", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("upper_bound", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("rate", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "lower_bound >= 0", name="ck_payroll_tax_bracket_lower_non_negative"
        ),
        sa.CheckConstraint(
            "rate >= 0", name="ck_payroll_tax_bracket_rate_non_negative"
        ),
        sa.CheckConstraint("rate <= 100", name="ck_payroll_tax_bracket_rate_maximum"),
        sa.CheckConstraint(
            "upper_bound IS NULL OR upper_bound > lower_bound",
            name="ck_payroll_tax_bracket_bounds",
        ),
        sa.CheckConstraint(
            "sort_order > 0", name="ck_payroll_tax_bracket_sort_order_positive"
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id"], ["payroll_rule_sets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_set_id", "lower_bound", name="uq_payroll_tax_bracket_lower_bound"
        ),
    )
    op.create_index(
        "ix_payroll_tax_brackets_rule_set_id", "payroll_tax_brackets", ["rule_set_id"]
    )

    op.create_table(
        "payroll_accounting_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("profile_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("salary_expense_account_id", sa.String(), nullable=False),
        sa.Column("employer_charge_account_id", sa.String(), nullable=False),
        sa.Column("employee_payable_account_id", sa.String(), nullable=False),
        sa.Column("tax_payable_account_id", sa.String(), nullable=False),
        sa.Column("social_payable_account_id", sa.String(), nullable=False),
        sa.Column("other_deduction_payable_account_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["journal_id"], ["journals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salary_expense_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employer_charge_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_payable_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tax_payable_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["social_payable_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["other_deduction_payable_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "profile_code", name="uq_payroll_accounting_profile_code"
        ),
    )
    op.create_index(
        "ix_payroll_accounting_profiles_organization_id",
        "payroll_accounting_profiles",
        ["organization_id"],
    )
    op.create_index(
        "ix_payroll_accounting_profiles_journal_id",
        "payroll_accounting_profiles",
        ["journal_id"],
    )

    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("period_code", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("rule_set_id", sa.String(), nullable=False),
        sa.Column("accounting_profile_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("gross_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "employee_contribution_total",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column(
            "employer_contribution_total",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column("tax_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "other_deduction_total", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("net_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("validated_by_user_id", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by_user_id", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_user_id", sa.String(), nullable=True),
        sa.Column("journal_entry_id", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("end_date >= start_date", name="ck_payroll_period_dates"),
        sa.CheckConstraint(
            "payment_date >= start_date", name="ck_payroll_period_payment_date"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'CALCULATED', 'VALIDATED', 'LOCKED', 'POSTED')",
            name="ck_payroll_period_status",
        ),
        sa.CheckConstraint(
            "gross_total >= 0", name="ck_payroll_period_gross_non_negative"
        ),
        sa.CheckConstraint("net_total >= 0", name="ck_payroll_period_net_non_negative"),
        sa.CheckConstraint(
            "employee_contribution_total >= 0",
            name="ck_payroll_period_employee_contribution_non_negative",
        ),
        sa.CheckConstraint(
            "employer_contribution_total >= 0",
            name="ck_payroll_period_employer_contribution_non_negative",
        ),
        sa.CheckConstraint("tax_total >= 0", name="ck_payroll_period_tax_non_negative"),
        sa.ForeignKeyConstraint(
            ["accounting_profile_id"],
            ["payroll_accounting_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id"], ["payroll_rule_sets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "period_code", name="uq_payroll_period_organization_code"
        ),
        sa.UniqueConstraint("journal_entry_id"),
    )
    op.create_index(
        "ix_payroll_periods_organization_id", "payroll_periods", ["organization_id"]
    )
    op.create_index("ix_payroll_periods_start_date", "payroll_periods", ["start_date"])
    op.create_index("ix_payroll_periods_end_date", "payroll_periods", ["end_date"])
    op.create_index("ix_payroll_periods_status", "payroll_periods", ["status"])

    op.create_table(
        "payroll_inputs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("payroll_period_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("input_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("input_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("taxable", sa.Boolean(), nullable=False),
        sa.Column("contribution_eligible", sa.Boolean(), nullable=False),
        sa.Column("source_reference", sa.String(length=100), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.CheckConstraint("amount >= 0", name="ck_payroll_input_amount_non_negative"),
        sa.CheckConstraint(
            "input_type IN ('EARNING', 'DEDUCTION')", name="ck_payroll_input_type"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["payroll_employees.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payroll_period_id"], ["payroll_periods.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payroll_period_id",
            "employee_id",
            "input_code",
            "source_reference",
            name="uq_payroll_input_period_employee_code_source",
        ),
    )
    op.create_index(
        "ix_payroll_inputs_organization_id", "payroll_inputs", ["organization_id"]
    )
    op.create_index(
        "ix_payroll_inputs_payroll_period_id", "payroll_inputs", ["payroll_period_id"]
    )
    op.create_index("ix_payroll_inputs_employee_id", "payroll_inputs", ["employee_id"])

    op.create_table(
        "payroll_slips",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("payroll_period_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("contract_id", sa.String(), nullable=False),
        sa.Column("slip_number", sa.String(length=100), nullable=False),
        sa.Column("correction_sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("base_salary", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "variable_earning_total", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("gross_salary", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "employee_contribution_total",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column(
            "employer_contribution_total",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column("income_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "other_deduction_total", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("net_salary", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("source_slip_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            "gross_salary >= 0", name="ck_payroll_slip_gross_non_negative"
        ),
        sa.CheckConstraint(
            "employee_contribution_total >= 0",
            name="ck_payroll_slip_employee_contribution_non_negative",
        ),
        sa.CheckConstraint(
            "employer_contribution_total >= 0",
            name="ck_payroll_slip_employer_contribution_non_negative",
        ),
        sa.CheckConstraint("income_tax >= 0", name="ck_payroll_slip_tax_non_negative"),
        sa.CheckConstraint(
            "other_deduction_total >= 0",
            name="ck_payroll_slip_other_deduction_non_negative",
        ),
        sa.CheckConstraint("net_salary >= 0", name="ck_payroll_slip_net_non_negative"),
        sa.CheckConstraint(
            "net_salary = gross_salary - employee_contribution_total - income_tax - other_deduction_total",
            name="ck_payroll_slip_net_consistency",
        ),
        sa.CheckConstraint(
            "correction_sequence >= 0", name="ck_payroll_slip_correction_sequence"
        ),
        sa.CheckConstraint(
            "status IN ('CALCULATED', 'VALIDATED', 'LOCKED', 'POSTED', 'CORRECTED')",
            name="ck_payroll_slip_status",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["payroll_contracts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["payroll_employees.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payroll_period_id"], ["payroll_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_slip_id"], ["payroll_slips.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payroll_period_id",
            "employee_id",
            "correction_sequence",
            name="uq_payroll_slip_period_employee_sequence",
        ),
    )
    op.create_index(
        "ix_payroll_slips_organization_id", "payroll_slips", ["organization_id"]
    )
    op.create_index(
        "ix_payroll_slips_payroll_period_id", "payroll_slips", ["payroll_period_id"]
    )
    op.create_index("ix_payroll_slips_employee_id", "payroll_slips", ["employee_id"])
    op.create_index("ix_payroll_slips_contract_id", "payroll_slips", ["contract_id"])
    op.create_index("ix_payroll_slips_status", "payroll_slips", ["status"])

    op.create_table(
        "payroll_slip_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("slip_id", sa.String(), nullable=False),
        sa.Column("line_type", sa.String(length=32), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("rate", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("cap_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "amount >= 0", name="ck_payroll_slip_line_amount_non_negative"
        ),
        sa.CheckConstraint(
            "base_amount >= 0", name="ck_payroll_slip_line_base_non_negative"
        ),
        sa.CheckConstraint("rate >= 0", name="ck_payroll_slip_line_rate_non_negative"),
        sa.CheckConstraint("rate <= 100", name="ck_payroll_slip_line_rate_maximum"),
        sa.CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="ck_payroll_slip_line_cap_non_negative",
        ),
        sa.CheckConstraint(
            "sort_order > 0", name="ck_payroll_slip_line_sort_order_positive"
        ),
        sa.CheckConstraint(
            "line_type IN ('BASE_SALARY', 'VARIABLE_EARNING', 'EMPLOYEE_CONTRIBUTION', 'EMPLOYER_CONTRIBUTION', 'INCOME_TAX', 'OTHER_DEDUCTION')",
            name="ck_payroll_slip_line_type",
        ),
        sa.ForeignKeyConstraint(["slip_id"], ["payroll_slips.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slip_id", "sort_order", name="uq_payroll_slip_line_order"),
    )
    op.create_index("ix_payroll_slip_lines_slip_id", "payroll_slip_lines", ["slip_id"])

    op.create_table(
        "payroll_corrections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("source_slip_id", sa.String(), nullable=False),
        sa.Column("resulting_slip_id", sa.String(), nullable=True),
        sa.Column("correction_number", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by_user_id", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'APPLIED', 'REJECTED')",
            name="ck_payroll_correction_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["resulting_slip_id"], ["payroll_slips.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_slip_id"], ["payroll_slips.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_slip_id",
            "correction_number",
            name="uq_payroll_correction_source_number",
        ),
    )
    op.create_index(
        "ix_payroll_corrections_organization_id",
        "payroll_corrections",
        ["organization_id"],
    )
    op.create_index(
        "ix_payroll_corrections_source_slip_id",
        "payroll_corrections",
        ["source_slip_id"],
    )
    op.create_index("ix_payroll_corrections_status", "payroll_corrections", ["status"])

    op.create_table(
        "payroll_audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("payroll_period_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payroll_period_id"], ["payroll_periods.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payroll_audit_events_organization_id",
        "payroll_audit_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_payroll_audit_events_payroll_period_id",
        "payroll_audit_events",
        ["payroll_period_id"],
    )
    op.create_index(
        "ix_payroll_audit_events_actor_user_id",
        "payroll_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_payroll_audit_events_action", "payroll_audit_events", ["action"]
    )
    op.create_index(
        "ix_payroll_audit_events_object_id", "payroll_audit_events", ["object_id"]
    )
    op.create_index(
        "ix_payroll_audit_events_occurred_at", "payroll_audit_events", ["occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("payroll_audit_events")
    op.drop_table("payroll_corrections")
    op.drop_table("payroll_slip_lines")
    op.drop_table("payroll_slips")
    op.drop_table("payroll_inputs")
    op.drop_table("payroll_periods")
    op.drop_table("payroll_accounting_profiles")
    op.drop_table("payroll_tax_brackets")
    op.drop_table("payroll_contribution_rules")
    op.drop_table("payroll_rule_sets")
    op.drop_table("payroll_contracts")
    op.drop_table("payroll_employees")
