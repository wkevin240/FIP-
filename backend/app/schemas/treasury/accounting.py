from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TreasuryAccountingProfileCreate(BaseModel):
    journal_id: str = Field(min_length=1)


class TreasuryAccountingProfileResponse(TreasuryAccountingProfileCreate):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TreasuryTransactionPostingCreate(BaseModel):
    counterpart_account_id: str = Field(min_length=1)


class TreasuryAccountingPostingResponse(BaseModel):
    id: str
    organization_id: str
    source_module: str
    source_type: str
    source_id: str
    journal_entry_id: str
    counterpart_account_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
