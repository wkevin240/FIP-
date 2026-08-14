from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DepreciationPlanResponse(BaseModel):
    id: str
    organization_id: str
    asset_id: str
    component_id: str
    version_number: int
    start_date: date
    end_date: date
    method: str
    useful_life_months: int
    declining_rate: Decimal | None
    acquisition_cost: Decimal
    residual_value: Decimal
    depreciable_base: Decimal
    convention: str
    parameters_snapshot: str
    status: str
    activated_at: datetime | None
    activated_by_user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepreciationScheduleLineResponse(BaseModel):
    id: str
    organization_id: str
    plan_id: str
    fiscal_period_id: str | None
    sequence_number: int
    scheduled_date: date
    opening_net_book_value: Decimal
    depreciation_amount: Decimal
    accumulated_depreciation: Decimal
    closing_net_book_value: Decimal
    status: str
    journal_entry_id: str | None
    posted_at: datetime | None
    posted_by_user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
