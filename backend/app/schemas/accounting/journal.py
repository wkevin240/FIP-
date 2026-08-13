from datetime import datetime

from app.core.enums.accounting import JournalType
from pydantic import BaseModel, ConfigDict, Field


class JournalBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    journal_type: JournalType = JournalType.GENERAL
    is_active: bool = True


class JournalCreate(JournalBase):
    pass


class JournalUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    journal_type: JournalType | None = None
    is_active: bool | None = None


class JournalResponse(JournalBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
