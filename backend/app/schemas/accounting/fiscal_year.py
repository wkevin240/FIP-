from datetime import date, datetime

from app.core.enums.accounting import FiscalYearStatus
from pydantic import BaseModel, ConfigDict


class FiscalYearBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    status: FiscalYearStatus = FiscalYearStatus.OPEN


class FiscalYearCreate(FiscalYearBase):
    pass


class FiscalYearUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: FiscalYearStatus | None = None


class FiscalYearResponse(FiscalYearBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
