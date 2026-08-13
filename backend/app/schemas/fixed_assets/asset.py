from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FixedAssetCreate(BaseModel):
    category_id: str
    asset_code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    serial_number: str | None = Field(None, max_length=128)
    acquisition_date: date
    acquisition_cost: Decimal = Field(..., ge=0, decimal_places=2)
    residual_value: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    currency: str = Field(default="XAF", min_length=3, max_length=3)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_values(self) -> "FixedAssetCreate":
        if self.residual_value > self.acquisition_cost:
            raise ValueError("Residual value cannot exceed acquisition cost")
        return self


class FixedAssetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    serial_number: str | None = Field(None, max_length=128)
    notes: str | None = None


class FixedAssetResponse(BaseModel):
    id: str
    organization_id: str
    category_id: str
    asset_code: str
    name: str
    description: str | None
    serial_number: str | None
    acquisition_date: date
    available_for_use_date: date | None
    acquisition_cost: Decimal
    residual_value: Decimal
    currency: str
    status: str
    acquisition_journal_entry_id: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FixedAssetComponentCreate(BaseModel):
    component_code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    acquisition_cost: Decimal = Field(..., ge=0, decimal_places=2)
    residual_value: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    useful_life_months: int = Field(..., gt=0)
    method: str = Field(pattern="^(STRAIGHT_LINE|DECLINING_BALANCE)$")
    declining_rate: Decimal | None = Field(default=None, gt=0, le=100, decimal_places=6)

    @model_validator(mode="after")
    def validate_component_values(self) -> "FixedAssetComponentCreate":
        if self.residual_value > self.acquisition_cost:
            raise ValueError("Component residual value cannot exceed acquisition cost")
        if self.method == "DECLINING_BALANCE" and self.declining_rate is None:
            raise ValueError("Declining balance component requires a declining rate")
        return self


class FixedAssetComponentResponse(FixedAssetComponentCreate):
    id: str
    organization_id: str
    asset_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FixedAssetAcquireRequest(BaseModel):
    fiscal_period_id: str
    reason: str | None = Field(None, max_length=1000)


class FixedAssetCommissionRequest(BaseModel):
    available_for_use_date: date
    reason: str | None = Field(None, max_length=1000)
