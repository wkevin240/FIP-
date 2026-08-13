from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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


class PayrollInput(Base):
    __tablename__ = "payroll_inputs"
    __table_args__ = (
        UniqueConstraint(
            "payroll_period_id",
            "employee_id",
            "input_code",
            "source_reference",
            name="uq_payroll_input_period_employee_code_source",
        ),
        CheckConstraint("amount >= 0", name="ck_payroll_input_amount_non_negative"),
        CheckConstraint(
            "input_type IN ('EARNING', 'DEDUCTION')", name="ck_payroll_input_type"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payroll_period_id = Column(
        String,
        ForeignKey("payroll_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    employee_id = Column(
        String,
        ForeignKey("payroll_employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    input_code = Column(String(64), nullable=False)
    description = Column(String(500), nullable=False)
    input_type = Column(String(16), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    taxable = Column(Boolean, nullable=False, default=True)
    contribution_eligible = Column(Boolean, nullable=False, default=True)
    source_reference = Column(String(100), nullable=True)
    created_by_user_id = Column(String, nullable=True)

    payroll_period = relationship("PayrollPeriod", back_populates="inputs")
    employee = relationship("Employee", back_populates="payroll_inputs")


class PayrollSlip(Base):
    __tablename__ = "payroll_slips"
    __table_args__ = (
        UniqueConstraint(
            "payroll_period_id",
            "employee_id",
            "correction_sequence",
            name="uq_payroll_slip_period_employee_sequence",
        ),
        CheckConstraint("gross_salary >= 0", name="ck_payroll_slip_gross_non_negative"),
        CheckConstraint(
            "employee_contribution_total >= 0",
            name="ck_payroll_slip_employee_contribution_non_negative",
        ),
        CheckConstraint(
            "employer_contribution_total >= 0",
            name="ck_payroll_slip_employer_contribution_non_negative",
        ),
        CheckConstraint("income_tax >= 0", name="ck_payroll_slip_tax_non_negative"),
        CheckConstraint(
            "other_deduction_total >= 0",
            name="ck_payroll_slip_other_deduction_non_negative",
        ),
        CheckConstraint("net_salary >= 0", name="ck_payroll_slip_net_non_negative"),
        CheckConstraint(
            "net_salary = gross_salary - employee_contribution_total - income_tax - other_deduction_total",
            name="ck_payroll_slip_net_consistency",
        ),
        CheckConstraint(
            "correction_sequence >= 0", name="ck_payroll_slip_correction_sequence"
        ),
        CheckConstraint(
            "status IN ('CALCULATED', 'VALIDATED', 'LOCKED', 'POSTED', 'CORRECTED')",
            name="ck_payroll_slip_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payroll_period_id = Column(
        String,
        ForeignKey("payroll_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    employee_id = Column(
        String,
        ForeignKey("payroll_employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_id = Column(
        String,
        ForeignKey("payroll_contracts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slip_number = Column(String(100), nullable=False)
    correction_sequence = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="CALCULATED", index=True)
    currency = Column(String(3), nullable=False, default="XAF")
    base_salary = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    variable_earning_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    gross_salary = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    employee_contribution_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    employer_contribution_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    income_tax = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    other_deduction_total = Column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    net_salary = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    source_slip_id = Column(
        String, ForeignKey("payroll_slips.id", ondelete="RESTRICT"), nullable=True
    )

    payroll_period = relationship("PayrollPeriod", back_populates="slips")
    employee = relationship("Employee", back_populates="slips")
    contract = relationship("EmploymentContract", back_populates="slips")
    lines = relationship(
        "PayrollSlipLine", back_populates="slip", cascade="all, delete-orphan"
    )
    source_slip = relationship("PayrollSlip", remote_side="PayrollSlip.id")
    corrections = relationship(
        "PayrollCorrection",
        foreign_keys="PayrollCorrection.source_slip_id",
        back_populates="source_slip",
    )


class PayrollSlipLine(Base):
    __tablename__ = "payroll_slip_lines"
    __table_args__ = (
        UniqueConstraint("slip_id", "sort_order", name="uq_payroll_slip_line_order"),
        CheckConstraint("amount >= 0", name="ck_payroll_slip_line_amount_non_negative"),
        CheckConstraint(
            "base_amount >= 0", name="ck_payroll_slip_line_base_non_negative"
        ),
        CheckConstraint("rate >= 0", name="ck_payroll_slip_line_rate_non_negative"),
        CheckConstraint("rate <= 100", name="ck_payroll_slip_line_rate_maximum"),
        CheckConstraint(
            "cap_amount IS NULL OR cap_amount >= 0",
            name="ck_payroll_slip_line_cap_non_negative",
        ),
        CheckConstraint(
            "sort_order > 0", name="ck_payroll_slip_line_sort_order_positive"
        ),
        CheckConstraint(
            "line_type IN ('BASE_SALARY', 'VARIABLE_EARNING', 'EMPLOYEE_CONTRIBUTION', 'EMPLOYER_CONTRIBUTION', 'INCOME_TAX', 'OTHER_DEDUCTION')",
            name="ck_payroll_slip_line_type",
        ),
    )

    slip_id = Column(
        String,
        ForeignKey("payroll_slips.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    line_type = Column(String(32), nullable=False)
    rule_code = Column(String(64), nullable=False)
    description = Column(String(500), nullable=False)
    base_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    rate = Column(Numeric(9, 6), nullable=False, default=Decimal("0.000000"))
    cap_amount = Column(Numeric(18, 2), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    sort_order = Column(Integer, nullable=False)

    slip = relationship("PayrollSlip", back_populates="lines")


class PayrollCorrection(Base):
    __tablename__ = "payroll_corrections"
    __table_args__ = (
        UniqueConstraint(
            "source_slip_id",
            "correction_number",
            name="uq_payroll_correction_source_number",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'APPLIED', 'REJECTED')",
            name="ck_payroll_correction_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_slip_id = Column(
        String,
        ForeignKey("payroll_slips.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    resulting_slip_id = Column(
        String, ForeignKey("payroll_slips.id", ondelete="RESTRICT"), nullable=True
    )
    correction_number = Column(String(64), nullable=False)
    reason = Column(String(1000), nullable=False)
    status = Column(String(32), nullable=False, default="REQUESTED", index=True)
    requested_by_user_id = Column(String, nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_by_user_id = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)

    source_slip = relationship(
        "PayrollSlip", foreign_keys=[source_slip_id], back_populates="corrections"
    )
    resulting_slip = relationship("PayrollSlip", foreign_keys=[resulting_slip_id])


class PayrollAuditEvent(Base):
    __tablename__ = "payroll_audit_events"

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payroll_period_id = Column(
        String,
        ForeignKey("payroll_periods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(String, nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    object_type = Column(String(64), nullable=False)
    object_id = Column(String, nullable=False, index=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(String(1000), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    payroll_period = relationship("PayrollPeriod", back_populates="audit_events")
