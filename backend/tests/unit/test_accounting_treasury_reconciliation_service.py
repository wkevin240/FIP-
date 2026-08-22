from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.services.treasury.accounting_treasury_reconciliation_service import (
    AccountingTreasuryReconciliationService,
)


class ScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


@pytest.mark.asyncio
async def test_reconciliation_is_not_ready_without_real_sources():
    session = AsyncMock()
    session.scalars.side_effect = [ScalarResult([]) for _ in range(8)]
    result = await AccountingTreasuryReconciliationService(session).report(
        "org-a", date(2026, 8, 22)
    )
    assert result.status == "NOT_READY"
    assert result.blockers == ["NO_PAYMENT_SOURCE", "NO_BANK_TRANSACTION_SOURCE"]
    assert result.amount_differences == Decimal("0.00")


@pytest.mark.asyncio
async def test_payment_without_posted_accounting_entry_is_incomplete():
    payment = SimpleNamespace(
        id="payment-1",
        amount=Decimal("100.00"),
        external_reference="BANK-1",
        payment_date=date(2026, 8, 22),
    )
    transaction = SimpleNamespace(
        id="bank-1",
        transaction_date=date(2026, 8, 22),
        external_id="BANK-1",
        reference=None,
        amount=Decimal("100.00"),
    )
    session = AsyncMock()
    session.scalars.side_effect = [
        ScalarResult([payment]),
        ScalarResult([]),
        ScalarResult([transaction]),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
    ]
    result = await AccountingTreasuryReconciliationService(session).report(
        "org-a", date(2026, 8, 22)
    )
    assert result.status == "INCOMPLETE"
    assert result.missing_postings == 1
    assert "PAYMENT_ACCOUNTING_POSTING_ABSENT" in result.blockers


async def _run_match(payment, transactions):
    session = AsyncMock()
    session.scalars.side_effect = [
        ScalarResult([payment]),
        ScalarResult([]),
        ScalarResult(transactions),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
        ScalarResult([]),
    ]
    return await AccountingTreasuryReconciliationService(session).report(
        "org-a", date(2026, 8, 22)
    )


@pytest.mark.asyncio
async def test_ambiguous_bank_candidates_are_never_selected_arbitrarily():
    payment = SimpleNamespace(
        id="payment-ambiguous",
        amount=Decimal("100.00"),
        external_reference="DUPLICATE",
        payment_date=date(2026, 8, 22),
    )
    transactions = [
        SimpleNamespace(
            id="bank-a",
            transaction_date=date(2026, 8, 22),
            external_id="DUPLICATE",
            reference=None,
            amount=Decimal("100.00"),
        ),
        SimpleNamespace(
            id="bank-b",
            transaction_date=date(2026, 8, 22),
            external_id="DUPLICATE",
            reference=None,
            amount=Decimal("100.00"),
        ),
    ]
    result = await _run_match(payment, transactions)
    assert result.matched_payments == 0
    assert result.unmatched_payments == 1
    assert "AMBIGUOUS_PAYMENT_BANK_MATCH" in result.blockers
    assert "BANK_TRANSACTION_WITHOUT_PAYMENT" in result.blockers


@pytest.mark.asyncio
async def test_wrong_date_is_distinguished_from_missing_reference():
    payment = SimpleNamespace(
        id="payment-date",
        amount=Decimal("100.00"),
        external_reference="DATE-MISMATCH",
        payment_date=date(2026, 8, 22),
    )
    transaction = SimpleNamespace(
        id="bank-date",
        transaction_date=date(2026, 8, 21),
        external_id="DATE-MISMATCH",
        reference=None,
        amount=Decimal("100.00"),
    )
    result = await _run_match(payment, [transaction])
    assert "PAYMENT_BANK_WRONG_DATE" in result.blockers
    assert "PAYMENT_BANK_WRONG_REFERENCE" not in result.blockers


@pytest.mark.asyncio
async def test_wrong_reference_is_distinguished_from_missing_transaction():
    payment = SimpleNamespace(
        id="payment-reference",
        amount=Decimal("100.00"),
        external_reference="EXPECTED",
        payment_date=date(2026, 8, 22),
    )
    transaction = SimpleNamespace(
        id="bank-reference",
        transaction_date=date(2026, 8, 22),
        external_id="OTHER",
        reference=None,
        amount=Decimal("100.00"),
    )
    result = await _run_match(payment, [transaction])
    assert "PAYMENT_BANK_WRONG_REFERENCE" in result.blockers
    assert "PAYMENT_BANK_WRONG_DATE" not in result.blockers


@pytest.mark.asyncio
async def test_amount_difference_is_returned_separately_with_decimal_precision():
    payment = SimpleNamespace(
        id="payment-amount",
        amount=Decimal("100.00"),
        external_reference="AMOUNT",
        payment_date=date(2026, 8, 22),
    )
    transaction = SimpleNamespace(
        id="bank-amount",
        transaction_date=date(2026, 8, 22),
        external_id="AMOUNT",
        reference=None,
        amount=Decimal("99.99"),
    )
    result = await _run_match(payment, [transaction])
    assert result.amount_differences == Decimal("0.01")
    assert "PAYMENT_BANK_AMOUNT_DIFFERENCE" in result.blockers


@pytest.mark.asyncio
async def test_no_bank_candidate_has_its_own_blocker():
    payment = SimpleNamespace(
        id="payment-none",
        amount=Decimal("100.00"),
        external_reference="MISSING",
        payment_date=date(2026, 8, 22),
    )
    transaction = SimpleNamespace(
        id="bank-other",
        transaction_date=date(2026, 8, 21),
        external_id="OTHER",
        reference=None,
        amount=Decimal("100.00"),
    )
    result = await _run_match(payment, [transaction])
    assert "PAYMENT_BANK_NO_CANDIDATE" in result.blockers
    assert "PAYMENT_BANK_WRONG_DATE" not in result.blockers
    assert "PAYMENT_BANK_WRONG_REFERENCE" not in result.blockers
