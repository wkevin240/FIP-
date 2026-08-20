from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.procurement import (
    SupplierPaymentAllocationCreate,
    SupplierPaymentReconciliationResponse,
)
from app.services.permission_service import PermissionService
from pydantic import ValidationError


def test_allocation_schema_uses_decimal_and_positive_amount():
    data = SupplierPaymentAllocationCreate(
        invoice_id="invoice-real", amount=Decimal("25.10")
    )
    assert data.amount == Decimal("25.10")
    with pytest.raises(ValidationError):
        SupplierPaymentAllocationCreate(
            invoice_id="invoice-real", amount=Decimal("0.00")
        )


def test_supplier_payment_reconciliation_states_are_explicit():
    base = {
        "payment_id": "payment-real",
        "organization_id": "org-real",
        "payment_amount": Decimal("100.00"),
        "allocation_count": 0,
    }
    assert (
        SupplierPaymentReconciliationResponse(
            **base,
            allocated_amount=Decimal("0.00"),
            unapplied_amount=Decimal("100.00"),
            status="UNAPPLIED",
        ).status
        == "UNAPPLIED"
    )
    assert (
        SupplierPaymentReconciliationResponse(
            **base,
            allocated_amount=Decimal("40.00"),
            unapplied_amount=Decimal("60.00"),
            status="PARTIALLY_ALLOCATED",
        ).status
        == "PARTIALLY_ALLOCATED"
    )
    assert (
        SupplierPaymentReconciliationResponse(
            **base,
            allocated_amount=Decimal("100.00"),
            unapplied_amount=Decimal("0.00"),
            status="FULLY_ALLOCATED",
        ).status
        == "FULLY_ALLOCATED"
    )


def test_supplier_payment_allocation_rbac_is_restricted():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "supplier_payment:allocate"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "supplier_payment:reallocate"
    )
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "supplier_payment:allocate"
    )
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "supplier_payment:reallocate"
    )
