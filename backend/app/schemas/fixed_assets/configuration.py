from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FixedAssetAccountingProfileCreate(BaseModel):
    profile_code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    journal_id: str
    asset_account_id: str
    accumulated_depreciation_account_id: str
    depreciation_expense_account_id: str
    acquisition_counterpart_account_id: str
    disposal_proceeds_account_id: str
    disposal_gain_account_id: str
    disposal_loss_account_id: str


class FixedAssetAccountingProfileResponse(FixedAssetAccountingProfileCreate):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FixedAssetCategoryCreate(BaseModel):
    accounting_profile_id: str
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    default_method: str = Field(
        default="STRAIGHT_LINE", pattern="^(STRAIGHT_LINE|DECLINING_BALANCE)$"
    )
    default_useful_life_months: int = Field(..., gt=0)
    default_residual_rate: Decimal = Field(
        default=Decimal("0.000000"), ge=0, le=100, decimal_places=6
    )
    default_declining_rate: Decimal | None = Field(
        default=None, gt=0, le=100, decimal_places=6
    )

    @model_validator(mode="after")
    def validate_method_parameters(self) -> "FixedAssetCategoryCreate":
        if (
            self.default_method == "DECLINING_BALANCE"
            and self.default_declining_rate is None
        ):
            raise ValueError("Declining balance category requires a declining rate")
        return self


class FixedAssetCategoryResponse(FixedAssetCategoryCreate):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
