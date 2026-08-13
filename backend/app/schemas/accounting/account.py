from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountBase(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=255)
    description: str | None = None
    is_active: bool = True
    account_type: str = Field(..., max_length=50)
    parent_id: str | None = None
    collective_account_id: str | None = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    account_type: str | None = Field(None, max_length=50)
    parent_id: str | None = None
    collective_account_id: str | None = None


class AccountResponse(AccountBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
