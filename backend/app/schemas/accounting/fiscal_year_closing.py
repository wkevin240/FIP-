from datetime import date

from app.core.enums.accounting import FiscalYearStatus
from pydantic import BaseModel, Field


class FiscalYearClosingPreviewResponse(BaseModel):
    fiscal_year_id: str
    start_date: date
    end_date: date
    current_status: FiscalYearStatus
    fiscal_period_count: int = Field(ge=0)
    open_period_count: int = Field(ge=0)
    locked_period_count: int = Field(ge=0)
    draft_entry_count: int = Field(ge=0)
    is_ready: bool
    blockers: list[str] = Field(default_factory=list)


class FiscalYearClosingResponse(FiscalYearClosingPreviewResponse):
    status: FiscalYearStatus
