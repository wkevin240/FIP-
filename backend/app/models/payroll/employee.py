from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Employee(Base):
    __tablename__ = "payroll_employees"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_payroll_employee_organization_code",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    employee_code = Column(String(64), nullable=False)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    email = Column(String(255), nullable=True)
    tax_identifier = Column(String(64), nullable=True)
    social_security_number = Column(String(64), nullable=True)
    hire_date = Column(Date, nullable=False)
    termination_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="payroll_employees")
    contracts = relationship("EmploymentContract", back_populates="employee")
    payroll_inputs = relationship("PayrollInput", back_populates="employee")
    slips = relationship("PayrollSlip", back_populates="employee")


class EmploymentContract(Base):
    __tablename__ = "payroll_contracts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "contract_number",
            name="uq_payroll_contract_organization_number",
        ),
        CheckConstraint(
            "base_salary >= 0", name="ck_payroll_contract_base_salary_non_negative"
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_payroll_contract_dates",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED')",
            name="ck_payroll_contract_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    employee_id = Column(
        String,
        ForeignKey("payroll_employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contract_number = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True, index=True)
    base_salary = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    currency = Column(String(3), nullable=False, default="XAF")
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="payroll_contracts")
    employee = relationship("Employee", back_populates="contracts")
    slips = relationship("PayrollSlip", back_populates="contract")
