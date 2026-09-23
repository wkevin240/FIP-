import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.customer_invoice import CustomerInvoiceStatus


class CustomerInvoiceCreate(BaseModel):
    customer_id: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    due_date: date
    currency_code: str = Field(min_length=3, max_length=3)
    subtotal: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    tax_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    total_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)

    @field_validator("customer_id", "invoice_number")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value, flags=re.ASCII):
            raise ValueError("currency_code must contain exactly three ASCII letters")
        return value

    @model_validator(mode="after")
    def validate_invoice(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date must be on or after invoice_date")
        if self.subtotal + self.tax_amount != self.total_amount:
            raise ValueError("total_amount must equal subtotal plus tax_amount")
        return self


class CustomerInvoiceUpdate(BaseModel):
    invoice_number: str | None = Field(default=None, min_length=1, max_length=100)
    invoice_date: date | None = None
    due_date: date | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)

    @field_validator("invoice_number")
    @classmethod
    def normalize_invoice_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("invoice_number must not be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value, flags=re.ASCII):
            raise ValueError("currency_code must contain exactly three ASCII letters")
        return value


class CustomerInvoiceResponse(BaseModel):
    id: str
    organization_id: str
    customer_id: str
    invoice_number: str
    invoice_date: date
    due_date: date
    currency_code: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: CustomerInvoiceStatus
    issued_at: datetime | None
    issued_by: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


