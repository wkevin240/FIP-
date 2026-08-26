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
        status="READY",
        candidates=[candidate],
    )
    assert preview.status == "READY"
    assert preview.candidates[0].status == "PROPOSED"
    assert preview.candidates[0].amount_difference == Decimal("0.00")


def test_supplier_payment_reconciliation_has_explicit_no_match_state():
    preview = SupplierPaymentReconciliationPreview(
        organization_id="org-real",
        bank_transaction_id="bank-real",
        bank_amount=Decimal("-20.00"),
        transaction_date=date(2026, 1, 10),
        status="NOT_READY",
        candidates=[],
    )
    assert preview.status == "NOT_READY"
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

    assert preview.status == "NOT_READY"
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_uses_canonical_full_allocation_and_is_read_only():
    from app.services.treasury.supplier_payment_reconciliation_service import (
        SupplierPaymentReconciliationService,
    )

    transaction = SimpleNamespace(
        id="bank-real",
        amount=Decimal("-100.00"),
        transaction_date=date(2026, 1, 10),
        reconciled_at=None,
        external_id="bank-ext",
        reference="bank-ref",
    )
    payment = SimpleNamespace(
        id="payment-real",
        amount=Decimal("100.00"),
        payment_date=date(2026, 1, 10),
        external_reference="bank-ext",
    )
    posting = SimpleNamespace(status="POSTED")
    entry = SimpleNamespace(id="entry-real")
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=transaction),
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(all=lambda: [(payment, posting, entry)]),
                SimpleNamespace(one=lambda: (Decimal("100.00"), 1)),
            ]
        ),
    )

    preview = await SupplierPaymentReconciliationService(session).preview(
        "org-real", "bank-real"
    )

    assert preview.status == "READY"
    assert preview.candidates[0].allocated_amount == Decimal("100.00")
    assert preview.candidates[0].unapplied_amount == Decimal("0.00")
    assert preview.candidates[0].allocation_count == 1
    assert preview.candidates[0].amount_difference == Decimal("0.00")
    assert not hasattr(session, "commit")


@pytest.mark.asyncio
async def test_preview_marks_partial_canonical_allocation_incomplete():
    from app.services.treasury.supplier_payment_reconciliation_service import (
        SupplierPaymentReconciliationService,
    )

    transaction = SimpleNamespace(
        id="bank-real",
        amount=Decimal("-100.00"),
        transaction_date=date(2026, 1, 10),
        reconciled_at=None,
        external_id="bank-ext",
        reference="bank-ref",
    )
    payment = SimpleNamespace(
        id="payment-real",
        amount=Decimal("100.00"),
        payment_date=date(2026, 1, 10),
        external_reference="bank-ext",
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=transaction),
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(
                    all=lambda: [
                        (
                            payment,
                            SimpleNamespace(status="POSTED"),
                            SimpleNamespace(id="entry-real"),
                        )
                    ]
                ),
                SimpleNamespace(one=lambda: (Decimal("60.00"), 1)),
            ]
        ),
    )

    preview = await SupplierPaymentReconciliationService(session).preview(
        "org-real", "bank-real"
    )

    candidate = preview.candidates[0]
    assert preview.status == "INCOMPLETE"
    assert candidate.status == "INCOMPLETE"
    assert candidate.allocated_amount == Decimal("60.00")
    assert candidate.unapplied_amount == Decimal("40.00")
    assert candidate.amount_difference == Decimal("40.00")
