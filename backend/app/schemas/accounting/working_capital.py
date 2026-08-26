from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class WorkingCapitalMetric(BaseModel):
    code: str
    value: Decimal | None
    status: str
    source: str
    explanation: str | None = None


class WorkingCapitalResponse(BaseModel):
    organization_id: str
    period_start: date
    as_of_date: date
    accounts_receivable: Decimal
    inventory_value: Decimal
    accounts_payable: Decimal
    operating_working_capital: Decimal
    dso: WorkingCapitalMetric
    dpo: WorkingCapitalMetric
    dio: WorkingCapitalMetric
    cash_conversion_cycle: WorkingCapitalMetric
