from datetime import date, datetime
from decimal import Decimal

from app.core.enums.invoicing import PaymentMethod
from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    invoice_id: str | None = None
    payment_date: date
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    method: PaymentMethod
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    id: str
    organization_id: str
    invoice_id: str | None = None
    payment_date: date
    amount: Decimal
    method: PaymentMethod
    external_reference: str | None
    received_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
