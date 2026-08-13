from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class JournalEntryLineCreate(BaseModel):
    account_id: str
    description: str | None = Field(None, max_length=500)
    debit: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2
    )
    credit: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2
    )


class JournalEntryLineResponse(JournalEntryLineCreate):
    id: str
    journal_entry_id: str
    line_number: int

    model_config = ConfigDict(from_attributes=True)
