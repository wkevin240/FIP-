from datetime import date
from decimal import Decimal

from app.core.enums.users import MembershipRole
from app.schemas.invoicing.payment import PaymentAllocationCreate
from app.services.invoicing.receivable_service import ReceivableService
from app.services.permission_service import PermissionService


def test_receivable_ageing_uses_reporting_date_and_due_date():
    as_of = date(2026, 8, 20)
    assert ReceivableService._age(date(2026, 8, 20), as_of, Decimal("100.00")) == (
        "CURRENT",
        Decimal("0.00"),
    )
    assert ReceivableService._age(date(2026, 8, 1), as_of, Decimal("100.00")) == (
        "1-30",
        Decimal("100.00"),
    )
    assert ReceivableService._age(date(2026, 6, 1), as_of, Decimal("100.00")) == (
        "61-90",
        Decimal("100.00"),
    )
    assert ReceivableService._age(None, as_of, Decimal("100.00")) == (
        "CURRENT",
        Decimal("0.00"),
    )
    assert ReceivableService._age(date(2026, 8, 1), as_of, Decimal("0.00")) == (
        None,
        Decimal("0.00"),
    )


def test_payment_allocation_is_decimal_and_idempotent_key_is_required():
    allocation = PaymentAllocationCreate(
        invoice_id="invoice-real",
        amount=Decimal("125.10"),
        idempotency_key="allocation-real-1",
    )
    assert allocation.amount == Decimal("125.10")
    assert allocation.idempotency_key == "allocation-real-1"


def test_receivable_read_and_allocate_permissions_are_explicit():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "receivable:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "payment:allocate"
    )
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "receivable:read"
    )
