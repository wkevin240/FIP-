from datetime import date
from decimal import Decimal

from app.schemas.treasury.supplier_payment_reconciliation import (
    SupplierPaymentReconciliationCandidate,
    SupplierPaymentReconciliationPreview,
)


def test_supplier_payment_reconciliation_preview_is_proposal_only():
    candidate = SupplierPaymentReconciliationCandidate(
        payment_id="payment-real",
        external_reference="SUP-REAL-001",
        payment_date=date(2026, 1, 10),
        payment_amount=Decimal("100.00"),
        bank_transaction_id="bank-real",
        bank_amount=Decimal("-100.00"),
        amount_difference=Decimal("0.00"),
        date_difference_days=0,
        journal_entry_id="entry-real",
        status="PROPOSED",
        match_reasons=["EXACT_AMOUNT", "EXACT_DATE"],
    )
    preview = SupplierPaymentReconciliationPreview(
        organization_id="org-real",
        bank_transaction_id="bank-real",
        bank_amount=Decimal("-100.00"),
        transaction_date=date(2026, 1, 10),
        status="CANDIDATES_FOUND",
        candidates=[candidate],
    )
    assert preview.status == "CANDIDATES_FOUND"
    assert preview.candidates[0].status == "PROPOSED"
    assert preview.candidates[0].amount_difference == Decimal("0.00")


def test_supplier_payment_reconciliation_has_explicit_no_match_state():
    preview = SupplierPaymentReconciliationPreview(
        organization_id="org-real",
        bank_transaction_id="bank-real",
        bank_amount=Decimal("-20.00"),
        transaction_date=date(2026, 1, 10),
        status="NO_MATCH",
        candidates=[],
    )
    assert preview.status == "NO_MATCH"
    assert preview.candidates == []
