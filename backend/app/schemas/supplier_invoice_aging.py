from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SupplierApprovedExposureAgingRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supplier_id: str
    supplier_name: str
    currency_code: str
    current_amount: Decimal
    overdue_1_30_amount: Decimal
    overdue_31_60_amount: Decimal
    overdue_61_90_amount: Decimal
    overdue_90_plus_amount: Decimal
    total_amount: Decimal


class SupplierApprovedExposureAgingResponse(BaseModel):
    as_of_date: date
    basis: str = "APPROVED supplier invoices; no payment allocation is deducted"
    rows: list[SupplierApprovedExposureAgingRow]
