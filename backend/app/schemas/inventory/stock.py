from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from app.core.enums.inventory import StockMovementType
from pydantic import BaseModel, ConfigDict, Field


class StockOperationBase(BaseModel):
    warehouse_id: str
    product_id: str
    movement_date: date
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class StockReceiptCreate(StockOperationBase):
    unit_cost: Decimal = Field(..., ge=0, max_digits=18, decimal_places=4)


class StockIssueCreate(StockOperationBase):
    pass


class StockAdjustmentCreate(StockOperationBase):
    direction: Literal["IN", "OUT"]
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )


class StockTransferCreate(BaseModel):
    source_warehouse_id: str
    destination_warehouse_id: str
    product_id: str
    movement_date: date
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class StockMovementResponse(BaseModel):
    id: str
    organization_id: str
    warehouse_id: str
    product_id: str
    movement_type: StockMovementType
    movement_date: date
    quantity: Decimal
    unit_cost: Decimal
    total_value: Decimal
    transfer_id: str | None
    reference: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockTransferResponse(BaseModel):
    transfer_id: str
    source_movement: StockMovementResponse
    destination_movement: StockMovementResponse


class StockBalanceResponse(BaseModel):
    id: str
    organization_id: str
    warehouse_id: str
    product_id: str
    quantity: Decimal
    total_value: Decimal
    average_unit_cost: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
