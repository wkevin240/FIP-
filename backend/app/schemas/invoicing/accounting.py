from datetime import datetime

from app.schemas.invoicing.invoice import InvoiceResponse
from pydantic import BaseModel, ConfigDict, Field


class InvoiceAccountingProfileCreate(BaseModel):
    journal_id: str = Field(min_length=1)
    receivable_account_id: str = Field(min_length=1)
    revenue_account_id: str = Field(min_length=1)
    collected_vat_account_id: str | None = Field(default=None, min_length=1)
    is_active: bool = True


class InvoiceAccountingProfileResponse(InvoiceAccountingProfileCreate):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceAccountingPostingResponse(BaseModel):
    id: str
    organization_id: str
    source_module: str
    source_type: str
    source_id: str
    journal_entry_id: str
    idempotency_key: str
    status: str
    created_at: datetime
    updated_at: datetime
    invoice: InvoiceResponse

    model_config = ConfigDict(from_attributes=True)
