from datetime import date
from decimal import Decimal

from app.schemas.treasury.banking_cross_reconciliation import (
    BankingCrossReconciliationResponse,
)


def test_cross_reconciliation_empty_source_is_incomplete():
    response = BankingCrossReconciliationResponse(
        organization_id="org-real",
        as_of=date(2026, 8, 20),
        status="INCOMPLETE",
        imported_transactions=0,
        reconciled_transactions=0,
        unresolved_transactions=0,
        bank_inflows=Decimal("0.00"),
        bank_outflows=Decimal("0.00"),
        net_bank_movement=Decimal("0.00"),
        ar_outstanding=Decimal("0.00"),
        ap_outstanding=Decimal("0.00"),
        status_counts={},
        blockers=["NO_BANK_TRANSACTIONS", "NO_OPEN_AR_SOURCE", "NO_OPEN_AP_SOURCE"],
    )
    assert response.status == "INCOMPLETE"
    assert response.blockers[0] == "NO_BANK_TRANSACTIONS"


def test_cross_reconciliation_decimal_net_is_exact():
    inflows = Decimal("1500.10")
    outflows = Decimal("425.05")
    response = BankingCrossReconciliationResponse(
        organization_id="org-real",
        as_of=date(2026, 8, 20),
        status="READY",
        imported_transactions=4,
        reconciled_transactions=4,
        unresolved_transactions=0,
        bank_inflows=inflows,
        bank_outflows=outflows,
        net_bank_movement=(inflows - outflows).quantize(Decimal("0.01")),
        ar_outstanding=Decimal("800.00"),
        ap_outstanding=Decimal("600.00"),
        status_counts={"RECONCILED": 4},
        blockers=[],
    )
    assert response.net_bank_movement == Decimal("1075.05")
    assert (
        response.reconciled_transactions + response.unresolved_transactions
        == response.imported_transactions
    )
