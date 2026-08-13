from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FixedAssetDisposalCreate(BaseModel):
    fiscal_period_id: str
    disposal_date: date
    disposal_type: str = Field(default="SALE", pattern="^(SALE|SCRAP|TRANSFER)$")
    proceeds: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    notes: str | None = None


class FixedAssetDisposalResponse(BaseModel):
    id: str
    organization_id: str
    asset_id: str
    disposal_date: date
    disposal_type: str
    proceeds: Decimal
    asset_cost: Decimal
    accumulated_depreciation: Decimal
    net_book_value: Decimal
    gain_amount: Decimal
    loss_amount: Decimal
    status: str
    journal_entry_id: str | None
    posted_at: datetime | None
    posted_by_user_id: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FixedAssetAuditEventResponse(BaseModel):
    id: str
    organization_id: str
    asset_id: str | None
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    previous_value: str | None
    new_value: str | None
    reason: str | None
    context_ip: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
