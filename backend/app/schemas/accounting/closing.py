from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PeriodClosingSummaryResponse(BaseModel):
    fiscal_period_id: str
    posted_entry_count: int
    posted_line_count: int
    total_debit: Decimal
    total_credit: Decimal
    control_hash: str


class PeriodClosingResponse(PeriodClosingSummaryResponse):
    id: str
    organization_id: str
    closed_by_user_id: str
    closed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
