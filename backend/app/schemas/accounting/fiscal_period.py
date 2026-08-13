from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional
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

class FiscalPeriodResponse(FiscalPeriodBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
