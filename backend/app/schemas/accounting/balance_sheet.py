from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CalculationSourceResponse(BaseModel):
    record_type: str
    record_id: str
    module: str


class BalanceSheetResultResponse(BaseModel):
    code: str
    formula: str
    rule_version: str
    status: str
    value: Decimal | None
    reason: str | None
    sources: list[CalculationSourceResponse]


class BalanceSheetReportResponse(BaseModel):
    organization_id: str
    fiscal_period_id: str | None
    start_date: date
    end_date: date
    rule_version: str
    results: list[BalanceSheetResultResponse]
