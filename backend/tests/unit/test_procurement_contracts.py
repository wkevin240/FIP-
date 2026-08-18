from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.procurement import PurchaseInvoiceCreate, PurchaseInvoiceLineCreate
from app.services.permission_service import PermissionService
from pydantic import ValidationError


def test_purchase_line_decimal_breakdown_is_exact():
    line = PurchaseInvoiceLineCreate(
        expense_account_id="expense-real",
        description="Service fournisseur",
        quantity=Decimal(3),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("19.25"),
    )
    assert line.line_subtotal == Decimal("300.00")
    assert line.tax_amount == Decimal("57.75")
    assert line.line_total == Decimal("357.75")


def test_purchase_invoice_rejects_due_date_before_invoice_date():
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate(
            supplier_id="supplier-real",
            invoice_number="INV-1",
            invoice_date=date(2026, 8, 20),
            due_date=date(2026, 8, 19),
            lines=[
                PurchaseInvoiceLineCreate(
                    expense_account_id="expense-real",
                    description="Service fournisseur",
                    quantity=Decimal(1),
                    unit_price=Decimal("100.00"),
                    tax_rate=Decimal(0),
                )
            ],
        )


def test_procurement_permissions_follow_least_privilege():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "supplier:create"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "purchase_invoice:post"
    )
    assert PermissionService.role_allows(
        MembershipRole.MANAGER.value, "purchase_invoice:read"
    )
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "purchase_invoice:post"
    )
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "supplier_payment:read"
    )
