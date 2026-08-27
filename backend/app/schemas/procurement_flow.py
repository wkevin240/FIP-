from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PurchaseRequestLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    estimated_unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )


class PurchaseRequestCreate(BaseModel):
    request_number: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1)
    lines: list[PurchaseRequestLineCreate] = Field(min_length=1)


class PurchaseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    request_number: str
    requester_user_id: str
    status: str
    purpose: str


class PurchaseOrderLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    sort_order: int = Field(gt=0)


class PurchaseOrderCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=64)
    supplier_id: str
    request_id: str | None = None
    order_date: date
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    supplier_id: str
    request_id: str | None
    order_number: str
    order_date: date
    status: str


class GoodsReceiptLineCreate(BaseModel):
    order_line_id: str
    received_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class GoodsReceiptCreate(BaseModel):
    receipt_number: str = Field(min_length=1, max_length=64)
    order_id: str
    receipt_date: date
    lines: list[GoodsReceiptLineCreate] = Field(min_length=1)


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    order_id: str
    receipt_number: str
    receipt_date: date
    receiver_user_id: str
    status: str


class ThreeWayMatchResponse(BaseModel):
    status: str
    organization_id: str
    purchase_order_id: str | None
    purchase_invoice_id: str | None
    ordered_amount: Decimal | None
    received_amount: Decimal | None
    invoiced_amount: Decimal | None
    ordered_quantity: Decimal | None
    received_quantity: Decimal | None
    invoiced_quantity: Decimal | None
    amount_difference: Decimal | None
    quantity_difference: Decimal | None
    blockers: list[str]
