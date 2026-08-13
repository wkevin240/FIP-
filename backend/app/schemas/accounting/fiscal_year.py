from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from app.core.enums.accounting import FiscalYearStatus

class FiscalYearBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    status: FiscalYearStatus = FiscalYearStatus.OPEN

class FiscalYearCreate(FiscalYearBase):
    pass

class FiscalYearUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[FiscalYearStatus] = None

class FiscalYearResponse(FiscalYearBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
