from decimal import Decimal

import pytest
from app.schemas.procurement_flow import (
    GoodsReceiptLineCreate,
    PurchaseOrderLineCreate,
    PurchaseRequestCreate,
    PurchaseRequestLineCreate,
)
from app.services.permission_service import PermissionService
from pydantic import ValidationError


def test_procurement_flow_preserves_decimal_quantities_and_prices():
    request = PurchaseRequestCreate(
        request_number="REQ-TEST",
        purpose="Test fixture only",
        lines=[
            PurchaseRequestLineCreate(
                description="Fixture item",
                quantity=Decimal("2.500"),
                estimated_unit_price=Decimal("125.40"),
            )
        ],
    )
    order_line = PurchaseOrderLineCreate(
        description="Fixture item",
        quantity=Decimal("2.500"),
        unit_price=Decimal("125.40"),
        sort_order=1,
    )
    receipt_line = GoodsReceiptLineCreate(
        order_line_id="line-id", received_quantity=Decimal("2.000")
    )
    assert request.lines[0].quantity == Decimal("2.500")
    assert order_line.unit_price == Decimal("125.40")
    assert receipt_line.received_quantity == Decimal("2.000")


def test_procurement_flow_rejects_non_positive_quantities():
    with pytest.raises(ValidationError):
        PurchaseRequestLineCreate(description="Invalid", quantity=Decimal(0))
    with pytest.raises(ValidationError):
        PurchaseOrderLineCreate(
            description="Invalid",
            quantity=Decimal(1),
            unit_price=Decimal(1),
            sort_order=0,
        )


def test_procurement_flow_rbac_is_explicit():
    assert PermissionService.role_allows("ACCOUNTANT", "purchase_request:create")
    assert PermissionService.role_allows("MANAGER", "purchase_request:approve")
    assert PermissionService.role_allows("MANAGER", "goods_receipt:create")
    assert not PermissionService.role_allows("USER", "purchase_order:create")
    assert not PermissionService.role_allows("AUDITOR", "goods_receipt:create")
