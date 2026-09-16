from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SupplierBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    legal_name: str = Field(..., min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("code", "trade_name", "tax_id", "phone", "address")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not value:
            raise ValueError("Supplier code cannot be blank")
        if any(char.isspace() for char in value):
            raise ValueError("Supplier code cannot contain whitespace")
        return value.upper()

    @field_validator("legal_name")
    @classmethod
    def normalize_and_validate_legal_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Supplier legal name cannot be blank")
        return value


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("trade_name", "tax_id", "phone", "address")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("legal_name")
    @classmethod
    def normalize_and_validate_legal_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Supplier legal name cannot be blank")
        return value


class SupplierResponse(SupplierBase):
    id: str
    organization_id: str
    is_active: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
