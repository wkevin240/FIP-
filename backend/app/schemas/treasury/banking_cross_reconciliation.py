from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class BankingCrossReconciliationResponse(BaseModel):
    organization_id: str
    as_of: date
    status: str
    imported_transactions: int
    reconciled_transactions: int
    unresolved_transactions: int
    bank_inflows: Decimal
    bank_outflows: Decimal
    net_bank_movement: Decimal
    ar_outstanding: Decimal
    ap_outstanding: Decimal
    status_counts: dict[str, int]
    blockers: list[str]
