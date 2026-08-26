from app.schemas.procurement_approval import PurchaseInvoiceApprovalDecision
from app.services.permission_service import PermissionService


def test_approval_decision_schema_accepts_only_business_decisions():
    assert PurchaseInvoiceApprovalDecision(decision="APPROVED").decision == "APPROVED"
    assert (
        PurchaseInvoiceApprovalDecision(
            decision="REJECTED", reason="Missing receiving evidence"
        ).reason
        == "Missing receiving evidence"
    )


def test_approval_rbac_preserves_separation_of_duties():
    assert PermissionService.role_allows(
        "ACCOUNTANT", "purchase_invoice:approval:request"
    )
    assert PermissionService.role_allows(
        "ACCOUNTANT", "purchase_invoice:approval:decide"
    )
    assert PermissionService.role_allows("MANAGER", "purchase_invoice:approval:decide")
    assert not PermissionService.role_allows(
        "USER", "purchase_invoice:approval:request"
    )
    assert not PermissionService.role_allows(
        "AUDITOR", "purchase_invoice:approval:decide"
    )
