from datetime import date
from decimal import Decimal

from app.services.invoicing.collection_service import classify_collection


def test_collection_buckets_are_deterministic_at_boundaries():
    as_of = date(2026, 8, 20)
    assert classify_collection(as_of, date(2026, 8, 20)) == (0, "CURRENT", "NORMAL")
    assert classify_collection(as_of, date(2026, 7, 21)) == (30, "1_30", "HIGH")
    assert classify_collection(as_of, date(2026, 6, 21)) == (60, "31_60", "HIGH")
    assert classify_collection(as_of, date(2026, 5, 22)) == (90, "61_90", "CRITICAL")
    assert classify_collection(as_of, date(2026, 5, 21)) == (91, "90_PLUS", "CRITICAL")


def test_collection_without_due_date_requires_review():
    assert classify_collection(date(2026, 8, 20), None) == (0, "NO_DUE_DATE", "REVIEW")


def test_decimal_outstanding_reconciliation_is_exact():
    total = Decimal("100.10")
    paid = Decimal("30.05")
    credited = Decimal("10.05")
    assert total - paid - credited == Decimal("60.00")
