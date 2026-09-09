from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: bool = True
    account_type: str = Field(..., min_length=1, max_length=50)
    parent_id: Optional[str] = None
    collective_account_id: Optional[str] = None

    @field_validator("code", "name", "account_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if any(char.isspace() for char in value):
            raise ValueError("Account code cannot contain whitespace")
        return value


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    account_type: Optional[str] = Field(None, min_length=1, max_length=50)
    parent_id: Optional[str] = None
    collective_account_id: Optional[str] = None

    @field_validator("name", "account_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class AccountResponse(AccountBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
