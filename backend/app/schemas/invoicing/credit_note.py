from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CreditNoteCreate(BaseModel):
    invoice_id: str
    credit_note_number: str = Field(..., min_length=1, max_length=64)
    credit_date: date
    subtotal: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)
    tax_amount: Decimal = Field(..., ge=0, max_digits=18, decimal_places=2)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(..., min_length=1, max_length=500)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_amount_breakdown(self) -> "CreditNoteCreate":
        if self.subtotal + self.tax_amount != self.amount:
            raise ValueError("Credit note subtotal plus tax amount must equal amount")
        return self

    @field_validator("credit_note_number")
    @classmethod
    def normalize_credit_note_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Credit note number must not be blank")
        return normalized


class CreditNoteResponse(BaseModel):
    id: str
    organization_id: str
    invoice_id: str
    credit_note_number: str
    credit_date: date
    subtotal: Decimal
    tax_amount: Decimal
    amount: Decimal
    reason: str
    issued_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
