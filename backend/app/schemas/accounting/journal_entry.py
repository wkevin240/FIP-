from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.accounting.journal_entry import JournalEntryStatus


class JournalEntryLineCreate(BaseModel):
    account_id: str = Field(min_length=1)
    description: str | None = None
    debit: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("account_id must not be blank")
        return value


class JournalEntryCreate(BaseModel):
    fiscal_period_id: str = Field(min_length=1)
    entry_date: date
    reference: str | None = None
    description: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=255)
    lines: list[JournalEntryLineCreate] = Field(min_length=2)

    @field_validator("description", "idempotency_key")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class JournalEntryReverse(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    entry_date: date | None = None
    reference: str | None = None
    description: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency_key must not be blank")
        return value

    @field_validator("reference", "description")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class JournalEntryLineResponse(JournalEntryLineCreate):
    id: str
    line_number: int
    model_config = ConfigDict(from_attributes=True)


class JournalEntryResponse(BaseModel):
    id: str
    organization_id: str
    fiscal_period_id: str
    entry_date: date
    reference: str | None
    description: str
    status: JournalEntryStatus
    idempotency_key: str
    posted_at: datetime | None
    posted_by: str | None
    reversal_of_id: str | None
    lines: list[JournalEntryLineResponse]
    model_config = ConfigDict(from_attributes=True)
