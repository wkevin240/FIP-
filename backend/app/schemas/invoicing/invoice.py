from datetime import date, datetime
from decimal import Decimal

from app.core.enums.invoicing import InvoiceStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InvoiceLineCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    product_id: str | None = None
    vat_rate_id: str | None = None
    quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=64)
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_tax_id: str | None = Field(default=None, max_length=64)
    customer_address: str | None = None
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    notes: str | None = None
    lines: list[InvoiceLineCreate] = Field(..., min_length=1)

    @field_validator("invoice_number")
    @classmethod
    def normalize_invoice_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Invoice number must not be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter alphabetic code")
        return normalized

    @model_validator(mode="after")
    def validate_due_date(self) -> "InvoiceCreate":
        if self.due_date is not None and self.due_date < self.invoice_date:
            raise ValueError("Invoice due date must not precede invoice date")
        return self


class InvoiceUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_tax_id: str | None = Field(default=None, max_length=64)
    customer_address: str | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceLineResponse(BaseModel):
    id: str
    invoice_id: str
    product_id: str | None
    vat_rate_id: str | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    line_subtotal: Decimal
    tax_amount: Decimal
    line_total: Decimal
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: str
    organization_id: str
    invoice_number: str
    customer_name: str
    customer_tax_id: str | None
    customer_address: str | None
    invoice_date: date
    due_date: date | None
    currency: str
    status: InvoiceStatus
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    credited_amount: Decimal
    outstanding_amount: Decimal
    issued_at: datetime | None
    cancelled_at: datetime | None
    notes: str | None
    lines: list[InvoiceLineResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
