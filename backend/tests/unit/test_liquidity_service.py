from datetime import date
from decimal import Decimal

import pytest
from app.schemas.accounting.liquidity import (
    LiquidityAccountPosition,
    LiquidityPositionResponse,
)
from app.services.accounting.liquidity_service import LiquidityService
from fastapi import HTTPException


def test_liquidity_date_validation_is_deterministic():
    with pytest.raises(HTTPException, match="period_start"):
        LiquidityService.validate_dates(date(2026, 2, 1), date(2026, 1, 31))


def test_liquidity_response_reconciles_cash_receivables_and_payables():
    position = LiquidityPositionResponse(
        organization_id="org-real",
        period_start=date(2026, 1, 1),
        as_of_date=date(2026, 1, 31),
        status="READY",
        available_cash=Decimal("1000.00"),
        receivables_outstanding=Decimal("250.00"),
        payables_outstanding=Decimal("125.00"),
        net_liquidity=Decimal("1125.00"),
        forecast_cash_status="NOT_READY",
        bank_accounts=[
            LiquidityAccountPosition(
                treasury_bank_account_id="bank-real",
                account_name="Real bank account",
                currency="XOF",
                opening_balance=Decimal("900.00"),
                movement_total=Decimal("100.00"),
                closing_balance=Decimal("1000.00"),
                inflows=Decimal("300.00"),
                outflows=Decimal("200.00"),
                transaction_count=2,
            )
        ],
        blockers=["CASH_FORECAST_MAPPING_NOT_CONFIGURED"],
    )
    assert position.net_liquidity == (
        position.available_cash
        + position.receivables_outstanding
        - position.payables_outstanding
    )
    assert position.forecast_cash_status == "NOT_READY"


def test_empty_liquidity_position_is_explicitly_not_ready():
    response = LiquidityPositionResponse(
        organization_id="org-real",
        period_start=date(2026, 1, 1),
        as_of_date=date(2026, 1, 31),
        status="NOT_READY",
        available_cash=Decimal("0.00"),
        receivables_outstanding=Decimal("0.00"),
        payables_outstanding=Decimal("0.00"),
        net_liquidity=Decimal("0.00"),
        forecast_cash_status="NOT_READY",
        bank_accounts=[],
        blockers=["NO_ACTIVE_TREASURY_BANK_ACCOUNT"],
    )
    assert response.status == "NOT_READY"
    assert response.bank_accounts == []
