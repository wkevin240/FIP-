from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums.accounting import FiscalPeriodStatus


class FiscalPeriodBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    status: FiscalPeriodStatus = FiscalPeriodStatus.OPEN
    fiscal_year_id: str


class FiscalPeriodCreate(FiscalPeriodBase):
    pass


class FiscalPeriodUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[FiscalPeriodStatus] = None


class FiscalPeriodReopen(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class FiscalPeriodResponse(FiscalPeriodBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FiscalPeriodCloseReadinessResponse(BaseModel):
    period_id: str
    organization_id: str
    status: FiscalPeriodStatus
    draft_journal_entries: int
    ledger_reconciled: bool
    ledger_balanced: bool
    ready_to_close: bool
    reconciliation: dict[str, object]
    balance_control: dict[str, object]
