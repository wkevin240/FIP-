from datetime import date, datetime

from app.core.enums.accounting import JournalEntryStatus
from app.schemas.accounting.journal_entry_line import (
    JournalEntryLineCreate,
    JournalEntryLineResponse,
)
from pydantic import BaseModel, ConfigDict, Field


class JournalEntryCreate(BaseModel):
    journal_id: str
    fiscal_period_id: str
    entry_number: str = Field(..., min_length=1, max_length=50)
    entry_date: date
    description: str = Field(..., min_length=1, max_length=500)
    reference: str | None = Field(None, max_length=100)
    lines: list[JournalEntryLineCreate] = Field(..., min_length=2)


class JournalEntryUpdate(BaseModel):
    entry_date: date | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    reference: str | None = Field(None, max_length=100)
    lines: list[JournalEntryLineCreate] | None = Field(None, min_length=2)


class JournalEntryReversalCreate(BaseModel):
    fiscal_period_id: str
    entry_date: date
    entry_number: str = Field(..., min_length=1, max_length=50)
    reason: str = Field(..., min_length=3, max_length=500)
    reference: str | None = Field(None, max_length=100)


class JournalEntryCorrectionCreate(BaseModel):
    reversal: JournalEntryReversalCreate
    correction: JournalEntryCreate


class JournalEntryResponse(BaseModel):
    id: str
    organization_id: str
    journal_id: str
    fiscal_period_id: str
    reversal_of_id: str | None
    reversal_reason: str | None
    voided_at: datetime | None
    voided_by_user_id: str | None
    entry_number: str
    entry_date: date
    description: str
    reference: str | None
    status: JournalEntryStatus
    posted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[JournalEntryLineResponse]

    model_config = ConfigDict(from_attributes=True)


class JournalEntryCorrectionResponse(BaseModel):
    original: JournalEntryResponse
    reversal: JournalEntryResponse
    correction: JournalEntryResponse
