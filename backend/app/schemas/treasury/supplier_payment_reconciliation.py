from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SupplierPaymentReconciliationCandidate(BaseModel):
    payment_id: str
    external_reference: str
    payment_date: date
    payment_amount: Decimal
    bank_transaction_id: str
    bank_amount: Decimal
    amount_difference: Decimal
    date_difference_days: int
    journal_entry_id: str
    status: str
    match_reasons: list[str]

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentReconciliationPreview(BaseModel):
    organization_id: str
    bank_transaction_id: str
    bank_amount: Decimal
    transaction_date: date
    status: str
    candidates: list[SupplierPaymentReconciliationCandidate]
