import re
from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.supplier_invoice import SupplierInvoiceStatus


class SupplierInvoiceBase(BaseModel):
    supplier_id: str = Field(..., min_length=1)
    invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_date: date
    due_date: date
    currency_code: str = Field(..., min_length=3, max_length=3)
    subtotal: Decimal = Field(..., ge=Decimal("0.00"))
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    total_amount: Decimal = Field(..., ge=Decimal("0.00"))
    description: str | None = None

    @field_validator("supplier_id", "invoice_number", "currency_code", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("invoice_number")
    @classmethod
    def validate_invoice_number(cls, value: str) -> str:
        if not value:
            raise ValueError("Invoice number cannot be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency code must be a three-letter code")
        return value

    @model_validator(mode="after")
    def validate_dates_and_total(self):
        if self.invoice_date > self.due_date:
            raise ValueError("Due date cannot be before invoice date")
        if self.total_amount != self.subtotal + self.tax_amount:
            raise ValueError("Total amount must equal subtotal plus tax amount")
        return self


class SupplierInvoiceCreate(SupplierInvoiceBase):
    pass


class SupplierInvoiceUpdate(BaseModel):
    invoice_number: str | None = Field(default=None, min_length=1, max_length=100)
    invoice_date: date | None = None
    due_date: date | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    tax_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    total_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    description: str | None = None

    @field_validator("invoice_number", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency code must be a three-letter code")
        return value


class SupplierInvoiceResponse(SupplierInvoiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    status: SupplierInvoiceStatus
    created_by: str
    updated_by: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("approved_at")
    @classmethod
    def require_timezone_aware_approval_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Approval timestamp must be timezone-aware")
        if value is not None and value.utcoffset() is None:
            raise ValueError("Approval timestamp must be timezone-aware")
        return value
