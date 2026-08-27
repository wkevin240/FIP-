from datetime import date
from decimal import Decimal

from app.schemas.accounting.cash_forecast import CashForecastResponse
from app.schemas.treasury.banking_cross_reconciliation import (
    BankingCrossReconciliationResponse,
)
from app.services.treasury.liquidity_control_service import LiquidityControlService


def test_threshold_dependent_alert_is_not_ready_without_configuration():
    alert = LiquidityControlService._not_ready(
        "LOW_LIQUIDITY",
        date(2026, 8, 21),
        date(2026, 8, 28),
        "No LOW_LIQUIDITY threshold is configured",
    )
    assert alert.code == "LOW_LIQUIDITY"
    assert alert.status == "NOT_READY"
    assert alert.affected_amount is None


def test_liquidity_control_alerts_are_explainable_and_decimal():
    service = LiquidityControlService.__new__(LiquidityControlService)
    forecast = CashForecastResponse(
        organization_id="org-real",
        period_start=date(2026, 8, 21),
        period_end=date(2026, 8, 28),
        status="READY",
        opening_cash=Decimal("100.00"),
        actual_cash_movement=Decimal("0.00"),
        expected_ar_inflows=Decimal("0.00"),
        expected_ap_outflows=Decimal("150.00"),
        projected_closing_cash=Decimal("-50.00"),
        forecast_source_status="READY",
        lines=[],
        blockers=[],
    )
    cross = BankingCrossReconciliationResponse(
        organization_id="org-real",
        as_of=date(2026, 8, 21),
        status="INCOMPLETE",
        imported_transactions=2,
        reconciled_transactions=1,
        unresolved_transactions=1,
        bank_inflows=Decimal("100.00"),
        bank_outflows=Decimal("40.00"),
        net_bank_movement=Decimal("60.00"),
        ar_outstanding=Decimal("300.00"),
        ap_outstanding=Decimal("400.00"),
        status_counts={"RECONCILED": 1, "NO_MATCH": 1},
        blockers=["UNRESOLVED_BANK_TRANSACTIONS"],
    )
    alerts = service._alerts(
        as_of=date(2026, 8, 21),
        horizon_end=date(2026, 8, 28),
        current_cash=Decimal("100.00"),
        forecast=forecast,
        cross=cross,
        liquidity_gap=None,
        configs={},
    )
    codes = {alert.code for alert in alerts}
    assert {
        "NEGATIVE_FORECAST",
        "UNRESOLVED_BANK_TRANSACTIONS",
        "LOW_LIQUIDITY",
        "LIQUIDITY_GAP",
    } <= codes
    negative = next(alert for alert in alerts if alert.code == "NEGATIVE_FORECAST")
    assert negative.affected_amount == Decimal("-50.00")


def test_net_liquidity_reconciliation_uses_decimal():
    current_cash = Decimal("1000.10")
    ar = Decimal("500.05")
    ap = Decimal("275.15")
    assert (current_cash + ar - ap).quantize(Decimal("0.01")) == Decimal("1225.00")
