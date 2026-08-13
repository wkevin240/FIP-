from datetime import datetime
from decimal import Decimal

from app.core.enums.inventory import StockUnit
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    unit: StockUnit = StockUnit.UNIT
    reorder_point: Decimal = Field(
        default=Decimal("0.000"), ge=0, max_digits=18, decimal_places=3
    )
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("SKU must not be blank")
        return normalized


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    unit: StockUnit | None = None
    reorder_point: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=3
    )
    is_active: bool | None = None


class ProductResponse(ProductBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
