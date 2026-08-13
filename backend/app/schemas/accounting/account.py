from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

class AccountBase(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    account_type: str = Field(..., max_length=50)
    parent_id: Optional[str] = None
    collective_account_id: Optional[str] = None

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    account_type: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[str] = None
    collective_account_id: Optional[str] = None

class AccountResponse(AccountBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
