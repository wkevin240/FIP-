from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CollectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: str
    invoice_number: str
    customer_name: str
    due_date: date | None
    total_amount: Decimal
    paid_amount: Decimal
    credited_amount: Decimal
    outstanding_amount: Decimal
    days_overdue: int
    ageing_bucket: str
    priority: str


class CollectionSummary(BaseModel):
    organization_id: str
    as_of: date
    status: str
    total_outstanding: Decimal
    overdue_outstanding: Decimal
    item_count: int
    items: list[CollectionItem]
    blockers: list[str]
