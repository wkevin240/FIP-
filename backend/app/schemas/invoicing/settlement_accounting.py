from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreditNotePostingResponse(BaseModel):
    id: str
    source_id: str
    journal_entry_id: str
    idempotency_key: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentPostingCreate(BaseModel):
    settlement_account_id: str = Field(min_length=1)


class PaymentPostingResponse(CreditNotePostingResponse):
    settlement_account_id: str
