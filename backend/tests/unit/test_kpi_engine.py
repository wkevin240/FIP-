from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from app.core.enums.users import MembershipRole
from app.schemas.accounting.financial_calculation import (
    ProfitabilityMetric,
    ProfitabilityResponse,
)
from app.schemas.accounting.kpi import KPIMetricResponse, KPIResponse
from app.services.accounting.kpi_service import KPIService
from app.services.permission_service import PermissionService


def test_kpi_response_preserves_decimal_and_explicit_not_ready_metrics():
    result = KPIResponse(
        organization_id="organization-real",
        fiscal_period_id=None,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status="READY",
        metrics=[
            KPIMetricResponse(
                code="REVENUE",
                name="REVENUE",
                label="Produits",
                status="READY",
                value=Decimal("100.00"),
                unit="amount",
                formula="credit - debit",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
            ),
            KPIMetricResponse(
                code="DSO",
                name="DSO",
                label="Délai moyen de recouvrement",
                status="NOT_READY",
                unit="days",
                formula="AR Outstanding / Revenue × days",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                reason="Mapping absent",
            ),
        ],
    )
    assert result.metrics[0].value == Decimal("100.00")
    assert result.metrics[1].status == "NOT_READY"
    assert result.metrics[1].value is None


def test_kpi_metric_with_ready_status_but_no_source_is_not_ready():
    source = ProfitabilityMetric(
        code="REVENUE",
        value=Decimal("100.00"),
        formula="credit - debit",
        status="READY",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        account_ids=["account-real"],
        journal_entry_line_ids=[],
        dimensions=[],
    )
    result = KPIService._metric(source, name="Produits")
    assert result.status == "NOT_READY"
    assert result.value is None
    assert result.reason == "No POSTED source lines exist in the requested scope"


async def test_kpi_calculation_consumes_central_profitability_metrics():
    period_start = date(2026, 1, 1)
    period_end = date(2026, 1, 31)
    metrics = [
        ProfitabilityMetric(
            code=code,
            value=value,
            formula=formula,
            status="READY",
            period_start=period_start,
            period_end=period_end,
            account_ids=[f"account-{code.lower()}"],
            journal_entry_line_ids=[f"line-{code.lower()}"],
            dimensions=[],
        )
        for code, value, formula in [
            ("REVENUE", Decimal("100.00"), "credit - debit"),
            ("COGS", Decimal("40.00"), "debit - credit"),
            ("OPERATING_EXPENSE", Decimal("20.00"), "debit - credit"),
            ("GROSS_PROFIT", Decimal("60.00"), "REVENUE - COGS"),
            (
                "OPERATING_INCOME",
                Decimal("40.00"),
                "REVENUE - COGS - OPERATING_EXPENSE",
            ),
            ("NET_INCOME", Decimal("40.00"), "REVENUE - COGS - OPERATING_EXPENSE"),
            ("GROSS_MARGIN", Decimal("0.60"), "GROSS_PROFIT / REVENUE"),
            ("OPERATING_MARGIN", Decimal("0.40"), "OPERATING_INCOME / REVENUE"),
            ("NET_MARGIN", Decimal("0.40"), "NET_INCOME / REVENUE"),
        ]
    ]
    profitability = ProfitabilityResponse(
        organization_id="organization-real",
        period_start=period_start,
        period_end=period_end,
        status="READY",
        metrics=metrics,
        source_line_count=len(metrics),
        ledger_is_balanced=True,
        ledger_balance_difference=Decimal("0.00"),
    )
    service = KPIService(None)
    service.calculation = AsyncMock()
    service.calculation.profitability.return_value = profitability

    result = await service.calculate(
        "organization-real", period_start=period_start, period_end=period_end
    )
    by_code = {metric.code: metric for metric in result.metrics}
    assert result.status == "INCOMPLETE"
    assert by_code["GROSS_PROFIT"].value == Decimal("60.00")
    assert by_code["GROSS_MARGIN"].value == Decimal("60.00")
    assert by_code["NET_MARGIN"].value == Decimal("40.00")
    assert by_code["DSO"].status == "NOT_READY"
    assert by_code["GROSS_PROFIT"].source_modules == ["Accounting"]
    service.calculation.profitability.assert_awaited_once_with(
        "organization-real", period_start, period_end, None, None
    )


def test_kpi_read_is_available_only_to_read_capable_roles():
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "kpi:read")
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "kpi:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "kpi:read")
    assert not PermissionService.role_allows(MembershipRole.USER.value, "kpi:read")
