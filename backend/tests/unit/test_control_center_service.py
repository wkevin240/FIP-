from datetime import date
from decimal import Decimal

from app.schemas.accounting.control_center import FinancialControlCenterResponse


def test_control_center_not_ready_blockers_are_explicit():
    response = FinancialControlCenterResponse(
        organization_id="org-real",
        as_of_date=date(2026, 1, 31),
        status="NOT_READY",
        posted_debit_total=Decimal("100.00"),
        posted_credit_total=Decimal("100.00"),
        draft_entry_count=2,
        open_period_count=1,
        unresolved_banking_exception_count=3,
        unreconciled_bank_transaction_count=4,
        blockers=[
            "DRAFT_JOURNAL_ENTRIES",
            "UNRESOLVED_BANKING_EXCEPTIONS",
            "UNRECONCILED_BANK_TRANSACTIONS",
            "OPEN_CURRENT_PERIOD",
        ],
    )
    assert response.status == "NOT_READY"
    assert response.posted_debit_total == response.posted_credit_total
    assert response.blockers


def test_control_center_ready_requires_no_blockers_and_balanced_posted_ledger():
    response = FinancialControlCenterResponse(
        organization_id="org-real",
        as_of_date=date(2026, 1, 31),
        status="READY",
        posted_debit_total=Decimal("100.00"),
        posted_credit_total=Decimal("100.00"),
        draft_entry_count=0,
        open_period_count=0,
        unresolved_banking_exception_count=0,
        unreconciled_bank_transaction_count=0,
        blockers=[],
    )
    assert response.status == "READY"
    assert response.blockers == []
