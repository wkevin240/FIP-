from decimal import Decimal

from app.core.enums.users import MembershipRole
from app.schemas.accounting.kpi import KPIMetricResponse, KPIResponse
from app.services.permission_service import PermissionService


def test_kpi_response_preserves_decimal_and_explicit_not_ready_metrics():
    result = KPIResponse(
        organization_id="organization-real",
        fiscal_period_id=None,
        status="READY",
        metrics=[
            KPIMetricResponse(
                code="REVENUE",
                label="Produits",
                status="READY",
                value=Decimal("100.00"),
                unit="amount",
            ),
            KPIMetricResponse(
                code="EBITDA",
                label="EBITDA",
                status="NOT_READY",
                unit="amount",
                reason="Mapping absent",
            ),
        ],
    )
    assert result.metrics[0].value == Decimal("100.00")
    assert result.metrics[1].status == "NOT_READY"
    assert result.metrics[1].value is None


def test_kpi_read_is_available_only_to_read_capable_roles():
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "kpi:read")
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "kpi:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "kpi:read")
    assert not PermissionService.role_allows(MembershipRole.USER.value, "kpi:read")
