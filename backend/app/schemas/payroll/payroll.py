from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PayrollInputCreate(BaseModel):
    employee_id: str
    input_code: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    input_type: str = Field(..., pattern="^(EARNING|DEDUCTION)$")
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    taxable: bool = True
    contribution_eligible: bool = True
    source_reference: str | None = Field(None, max_length=100)


class PayrollInputResponse(PayrollInputCreate):
    id: str
    organization_id: str
    payroll_period_id: str
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollSlipLineResponse(BaseModel):
    id: str
    line_type: str
    rule_code: str
    description: str
    base_amount: Decimal
    rate: Decimal
    cap_amount: Decimal | None
    amount: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class PayrollSlipResponse(BaseModel):
    id: str
    organization_id: str
    payroll_period_id: str
    employee_id: str
    contract_id: str
    slip_number: str
    correction_sequence: int
    status: str
    currency: str
    base_salary: Decimal
    variable_earning_total: Decimal
    gross_salary: Decimal
    employee_contribution_total: Decimal
    employer_contribution_total: Decimal
    income_tax: Decimal
    other_deduction_total: Decimal
    net_salary: Decimal
    calculated_at: datetime
    validated_at: datetime | None
    locked_at: datetime | None
    posted_at: datetime | None
    source_slip_id: str | None
    lines: list[PayrollSlipLineResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollCorrectionCreate(BaseModel):
    correction_number: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=3, max_length=1000)


class PayrollCorrectionResponse(BaseModel):
    id: str
    organization_id: str
    source_slip_id: str
    resulting_slip_id: str | None
    correction_number: str
    reason: str
    status: str
    requested_by_user_id: str
    requested_at: datetime
    approved_by_user_id: str | None
    approved_at: datetime | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollAuditEventResponse(BaseModel):
    id: str
    organization_id: str
    payroll_period_id: str | None
    actor_user_id: str | None
    action: str
    object_type: str
    object_id: str
    previous_value: str | None
    new_value: str | None
    reason: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
