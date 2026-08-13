from datetime import date, datetime
from decimal import Decimal

from app.core.enums.accounting import VATDirection
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VATRateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=100)
    rate: Decimal = Field(..., ge=0, le=100, max_digits=5, decimal_places=2)
    effective_from: date
    effective_to: date | None = None
    input_vat_account_id: str | None = None
    output_vat_account_id: str | None = None

    @model_validator(mode="after")
    def validate_effective_dates(self) -> "VATRateCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Effective end date must not precede effective start date")
        return self


class VATRateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    effective_to: date | None = None
    input_vat_account_id: str | None = None
    output_vat_account_id: str | None = None
    is_active: bool | None = None


class VATRateResponse(VATRateCreate):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VATCalculationRequest(BaseModel):
    vat_rate_id: str
    tax_date: date
    taxable_amount: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)


class VATCalculationResponse(VATCalculationRequest):
    vat_amount: Decimal
    total_amount: Decimal


class VATEntryCreate(VATCalculationRequest):
    journal_entry_id: str
    direction: VATDirection


class VATEntryResponse(VATEntryCreate):
    id: str
    organization_id: str
    vat_amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VATSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_output_vat: Decimal
    total_input_vat: Decimal
    net_vat_payable: Decimal
