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
    assert "PAYMENT_ACCOUNTING_POSTING_NOT_READY" in result.blockers
