from decimal import Decimal

from pydantic import BaseModel


class KPIMetricResponse(BaseModel):
    code: str
    label: str
    status: str
    value: Decimal | None = None
    unit: str
    reason: str | None = None


class KPIResponse(BaseModel):
    organization_id: str
    fiscal_period_id: str | None
    status: str
    metrics: list[KPIMetricResponse]
