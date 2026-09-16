from datetime import date
from decimal import Decimal

from app.domain.ap_aging import ApprovedExposureBucket, add_exposure, classify_due_date, empty_bucket_totals


AS_OF = date(2026, 9, 16)


def test_due_on_as_of_date_is_current() -> None:
    assert classify_due_date(AS_OF, AS_OF) == ApprovedExposureBucket.CURRENT


def test_overdue_boundaries_are_inclusive() -> None:
    assert classify_due_date(date(2026, 9, 15), AS_OF) == ApprovedExposureBucket.OVERDUE_1_30
    assert classify_due_date(date(2026, 8, 17), AS_OF) == ApprovedExposureBucket.OVERDUE_1_30
    assert classify_due_date(date(2026, 7, 18), AS_OF) == ApprovedExposureBucket.OVERDUE_31_60
    assert classify_due_date(date(2026, 6, 18), AS_OF) == ApprovedExposureBucket.OVERDUE_61_90
    assert classify_due_date(date(2026, 6, 17), AS_OF) == ApprovedExposureBucket.OVERDUE_90_PLUS


def test_exposure_aggregation_preserves_decimal_amounts() -> None:
    totals = empty_bucket_totals()
    add_exposure(totals, due_date=AS_OF, as_of_date=AS_OF, amount=Decimal("100.10"))
    add_exposure(totals, due_date=date(2026, 9, 1), as_of_date=AS_OF, amount=Decimal("0.20"))
    add_exposure(totals, due_date=date(2026, 8, 1), as_of_date=AS_OF, amount=Decimal("30.30"))

    assert totals[ApprovedExposureBucket.CURRENT] == Decimal("100.10")
    assert totals[ApprovedExposureBucket.OVERDUE_1_30] == Decimal("0.20")
    assert totals[ApprovedExposureBucket.OVERDUE_31_60] == Decimal("30.30")
    assert sum(totals.values(), Decimal("0.00")) == Decimal("130.60")
