from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PayrollRuleSet(Base):
    __tablename__ = "payroll_rule_sets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            "effective_from",
            name="uq_payroll_rule_set_organization_code_effective",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_payroll_rule_set_dates",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    currency = Column(String(3), nullable=False, default="XAF")
    professional_expense_rate = Column(
        Numeric(9, 6), nullable=False, default=Decimal("0.000000")
    )
    professional_expense_cap = Column(Numeric(18, 2), nullable=True)
    annual_tax_allowance = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    local_surtax_rate = Column(
        Numeric(9, 6), nullable=False, default=Decimal("0.000000")
    )
    is_active = Column(Boolean, nullable=False, default=True)
    source_reference = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="payroll_rule_sets")
    contribution_rules = relationship(
        "PayrollContributionRule",
        back_populates="rule_set",
        cascade="all, delete-orphan",
    )
    tax_brackets = relationship(
        "PayrollTaxBracket", back_populates="rule_set", cascade="all, delete-orphan"
    )
    periods = relationship("PayrollPeriod", back_populates="rule_set")


class PayrollContributionRule(Base):
    __tablename__ = "payroll_contribution_rules"
    __table_args__ = (
        UniqueConstraint(
            "rule_set_id", "code", name="uq_payroll_contribution_rule_set_code"
        ),
        CheckConstraint("rate >= 0", name="ck_payroll_contribution_rate_non_negative"),
        CheckConstraint("rate <= 100", name="ck_payroll_contribution_rate_maximum"),
        CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="ck_payroll_contribution_cap_non_negative",
        ),
        CheckConstraint(
            "direction IN ('EMPLOYEE', 'EMPLOYER')",
            name="ck_payroll_contribution_direction",
        ),
        CheckConstraint(
            "base_type IN ('GROSS', 'TAXABLE_GROSS')",
            name="ck_payroll_contribution_base_type",
        ),
        CheckConstraint(
            "sort_order > 0", name="ck_payroll_contribution_sort_order_positive"
        ),
    )

    rule_set_id = Column(
        String,
        ForeignKey("payroll_rule_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    direction = Column(String(16), nullable=False)
    base_type = Column(String(32), nullable=False, default="GROSS")
    rate = Column(Numeric(9, 6), nullable=False)
    cap_amount = Column(Numeric(18, 2), nullable=True)
    sort_order = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    rule_set = relationship("PayrollRuleSet", back_populates="contribution_rules")


class PayrollTaxBracket(Base):
    __tablename__ = "payroll_tax_brackets"
    __table_args__ = (
        UniqueConstraint(
            "rule_set_id", "lower_bound", name="uq_payroll_tax_bracket_lower_bound"
        ),
        CheckConstraint(
            "lower_bound >= 0", name="ck_payroll_tax_bracket_lower_non_negative"
        ),
        CheckConstraint("rate >= 0", name="ck_payroll_tax_bracket_rate_non_negative"),
        CheckConstraint("rate <= 100", name="ck_payroll_tax_bracket_rate_maximum"),
        CheckConstraint(
            "upper_bound IS NULL OR upper_bound > lower_bound",
            name="ck_payroll_tax_bracket_bounds",
        ),
        CheckConstraint(
            "sort_order > 0", name="ck_payroll_tax_bracket_sort_order_positive"
        ),
    )

    rule_set_id = Column(
        String,
        ForeignKey("payroll_rule_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lower_bound = Column(Numeric(18, 2), nullable=False)
    upper_bound = Column(Numeric(18, 2), nullable=True)
    rate = Column(Numeric(9, 6), nullable=False)
    sort_order = Column(Integer, nullable=False)

    rule_set = relationship("PayrollRuleSet", back_populates="tax_brackets")


class PayrollAccountingProfile(Base):
    __tablename__ = "payroll_accounting_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "profile_code", name="uq_payroll_accounting_profile_code"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    profile_code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    journal_id = Column(
        String,
        ForeignKey("journals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    salary_expense_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    employer_charge_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    employee_payable_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    tax_payable_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    social_payable_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    other_deduction_payable_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship(
        "Organization", back_populates="payroll_accounting_profiles"
    )
    periods = relationship("PayrollPeriod", back_populates="accounting_profile")


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "period_code", name="uq_payroll_period_organization_code"
        ),
        CheckConstraint("end_date >= start_date", name="ck_payroll_period_dates"),
        CheckConstraint(
            "payment_date >= start_date", name="ck_payroll_period_payment_date"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'CALCULATED', 'VALIDATED', 'LOCKED', 'POSTED')",
            name="ck_payroll_period_status",
        ),
        CheckConstraint(
            "gross_total >= 0", name="ck_payroll_period_gross_non_negative"
        ),
        CheckConstraint("net_total >= 0", name="ck_payroll_period_net_non_negative"),
        CheckConstraint(
            "employee_contribution_total >= 0",
            name="ck_payroll_period_employee_contribution_non_negative",
        ),
        CheckConstraint(
            "employer_contribution_total >= 0",
            name="ck_payroll_period_employer_contribution_non_negative",
        ),
        CheckConstraint("tax_total >= 0", name="ck_payroll_period_tax_non_negative"),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_code = Column(String(64), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    payment_date = Column(Date, nullable=False)
    fiscal_period_id = Column(
        String, ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False
    )
    rule_set_id = Column(
        String,
        ForeignKey("payroll_rule_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accounting_profile_id = Column(
        String,
        ForeignKey("payroll_accounting_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    gross_total = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    employee_contribution_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    employer_contribution_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    tax_total = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    other_deduction_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    net_total = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    calculated_at = Column(DateTime, nullable=True)
    validated_at = Column(DateTime, nullable=True)
    validated_by_user_id = Column(String, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by_user_id = Column(String, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    posted_by_user_id = Column(String, nullable=True)
    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="payroll_periods")
    rule_set = relationship("PayrollRuleSet", back_populates="periods")
    accounting_profile = relationship(
        "PayrollAccountingProfile", back_populates="periods"
    )
    inputs = relationship("PayrollInput", back_populates="payroll_period")
    slips = relationship("PayrollSlip", back_populates="payroll_period")
    audit_events = relationship("PayrollAuditEvent", back_populates="payroll_period")
