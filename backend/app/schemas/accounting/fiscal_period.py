from datetime import date, datetime

from app.core.enums.accounting import FiscalPeriodStatus
from pydantic import BaseModel, ConfigDict


class FiscalPeriodBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    status: FiscalPeriodStatus = FiscalPeriodStatus.OPEN
    fiscal_year_id: str


class FiscalPeriodCreate(FiscalPeriodBase):
    pass


class FiscalPeriodUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: FiscalPeriodStatus | None = None


class FiscalPeriodResponse(FiscalPeriodBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
