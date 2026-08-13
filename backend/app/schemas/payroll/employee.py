from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EmployeeCreate(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=64)
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    email: str | None = Field(None, max_length=255)
    tax_identifier: str | None = Field(None, max_length=64)
    social_security_number: str | None = Field(None, max_length=64)
    hire_date: date
    notes: str | None = None


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=128)
    last_name: str | None = Field(None, min_length=1, max_length=128)
    email: str | None = Field(None, max_length=255)
    tax_identifier: str | None = Field(None, max_length=64)
    social_security_number: str | None = Field(None, max_length=64)
    termination_date: date | None = None
    is_active: bool | None = None
    notes: str | None = None


class EmployeeResponse(BaseModel):
    id: str
    organization_id: str
    employee_code: str
    first_name: str
    last_name: str
    email: str | None
    tax_identifier: str | None
    social_security_number: str | None
    hire_date: date
    termination_date: date | None
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmploymentContractCreate(BaseModel):
    contract_number: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date | None = None
    base_salary: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="XAF", min_length=3, max_length=3)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_dates(self) -> "EmploymentContractCreate":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Contract end date cannot precede start date")
        return self


class EmploymentContractUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    end_date: date | None = None
    base_salary: Decimal | None = Field(None, ge=0, decimal_places=2)
    status: str | None = Field(None, pattern="^(DRAFT|ACTIVE|SUSPENDED|TERMINATED)$")
    notes: str | None = None


class EmploymentContractResponse(BaseModel):
    id: str
    organization_id: str
    employee_id: str
    contract_number: str
    title: str
    start_date: date
    end_date: date | None
    base_salary: Decimal
    currency: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
