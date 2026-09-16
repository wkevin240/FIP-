from datetime import date
from decimal import Decimal
from enum import StrEnum


class ApprovedExposureBucket(StrEnum):
    CURRENT = "CURRENT"
    OVERDUE_1_30 = "OVERDUE_1_30"
    OVERDUE_31_60 = "OVERDUE_31_60"
    OVERDUE_61_90 = "OVERDUE_61_90"
    OVERDUE_90_PLUS = "OVERDUE_90_PLUS"


def classify_due_date(due_date: date, as_of_date: date) -> ApprovedExposureBucket:
    if due_date >= as_of_date:
        return ApprovedExposureBucket.CURRENT

    days_overdue = (as_of_date - due_date).days
    if days_overdue <= 30:
        return ApprovedExposureBucket.OVERDUE_1_30
    if days_overdue <= 60:
        return ApprovedExposureBucket.OVERDUE_31_60
    if days_overdue <= 90:
        return ApprovedExposureBucket.OVERDUE_61_90
    return ApprovedExposureBucket.OVERDUE_90_PLUS


def empty_bucket_totals() -> dict[ApprovedExposureBucket, Decimal]:
    return {bucket: Decimal("0.00") for bucket in ApprovedExposureBucket}


def add_exposure(
    totals: dict[ApprovedExposureBucket, Decimal],
    *,
    due_date: date,
    as_of_date: date,
    amount: Decimal,
) -> None:
    totals[classify_due_date(due_date, as_of_date)] += amount
