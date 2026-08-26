from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
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


@pytest.mark.asyncio
async def test_preview_query_only_considers_outgoing_posted_entries():
    from app.services.treasury.supplier_payment_reconciliation_service import (
        SupplierPaymentReconciliationService,
    )

    session = SimpleNamespace(
        scalar=AsyncMock(
            return_value=SimpleNamespace(
                id="bank-real",
                amount=Decimal("100.00"),
                transaction_date=date(2026, 1, 10),
                reconciled_at=None,
                external_id="bank-ext",
                reference="bank-ref",
            )
        ),
        execute=AsyncMock(return_value=SimpleNamespace(all=list)),
    )

    preview = await SupplierPaymentReconciliationService(session).preview(
        "org-real", "bank-real"
    )

    assert preview.status == "NO_MATCH"
    query = session.execute.await_args.args[0]
    criteria_sql = " AND ".join(str(clause) for clause in query._where_criteria)
    assert "bank_transactions.amount < :amount_1" in criteria_sql
    assert "journal_entries.status = :status_1" in criteria_sql
