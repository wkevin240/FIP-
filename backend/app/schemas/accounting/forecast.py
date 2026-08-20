from decimal import Decimal

from pydantic import BaseModel, model_validator


class ForecastLineResponse(BaseModel):
    budget_id: str
    scenario_id: str
    fiscal_period_id: str
    account_id: str
    dimension_value_id: str | None
    actual_amount: Decimal
    approved_budget_amount: Decimal
    scenario_assumption_amount: Decimal
    forecast_amount: Decimal
    status: str

    @model_validator(mode="after")
    def verify_formula(self) -> "ForecastLineResponse":
        expected = (
            self.actual_amount
            + self.approved_budget_amount
            + self.scenario_assumption_amount
        )
        if self.forecast_amount != expected:
            raise ValueError(
                "forecast_amount must equal actual + approved budget + scenario assumption"
            )
        return self


class ForecastResponse(BaseModel):
    budget_id: str
    scenario_id: str
    status: str
    lines: list[ForecastLineResponse]
