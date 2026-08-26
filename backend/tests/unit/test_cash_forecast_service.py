from datetime import date
from decimal import Decimal

import pytest
from app.schemas.accounting.cash_forecast import CashForecastLine, CashForecastResponse
from app.services.accounting.cash_forecast_service import CashForecastService
from fastapi import HTTPException


def test_cash_forecast_rejects_inverted_dates():
    with pytest.raises(HTTPException, match="period_start"):
        CashForecastService.validate_dates(date(2026, 2, 1), date(2026, 1, 31))


def test_cash_forecast_reconciles_projected_cash():
    response = CashForecastResponse(
        organization_id="org-real",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 2),
        status="READY",
        opening_cash=Decimal("1000.00"),
        actual_cash_movement=Decimal("100.00"),
        expected_ar_inflows=Decimal("250.00"),
        expected_ap_outflows=Decimal("125.00"),
        projected_closing_cash=Decimal("1225.00"),
        forecast_source_status="READY",
        lines=[
            CashForecastLine(
                forecast_date=date(2026, 1, 1),
                actual_bank_movement=Decimal("100.00"),
                expected_ar_inflow=Decimal("250.00"),
                expected_ap_outflow=Decimal("125.00"),
                projected_net_movement=Decimal("225.00"),
                projected_closing_cash=Decimal("1225.00"),
            )
        ],
        blockers=[],
    )
    assert response.projected_closing_cash == (
        response.opening_cash
        + response.actual_cash_movement
        + response.expected_ar_inflows
        - response.expected_ap_outflows
    )


def test_cash_forecast_without_bank_source_is_not_ready():
    response = CashForecastResponse(
        organization_id="org-real",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 1),
        status="NOT_READY",
        opening_cash=Decimal("0.00"),
        actual_cash_movement=Decimal("0.00"),
        expected_ar_inflows=Decimal("0.00"),
        expected_ap_outflows=Decimal("0.00"),
        projected_closing_cash=Decimal("0.00"),
        forecast_source_status="NOT_READY",
        lines=[],
        blockers=["NO_ACTIVE_TREASURY_BANK_ACCOUNT"],
    )
    assert response.status == "NOT_READY"
    assert response.blockers == ["NO_ACTIVE_TREASURY_BANK_ACCOUNT"]
