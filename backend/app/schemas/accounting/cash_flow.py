from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CashFlowAccountMappingCreate(BaseModel):
    account_id: str
    is_cash_account: bool = False
    cash_flow_category: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_role(self) -> "CashFlowAccountMappingCreate":
        category = (
            self.cash_flow_category.strip().upper()
            if self.cash_flow_category is not None
            else None
        )
        if self.is_cash_account and category is not None:
            raise ValueError("Cash accounts cannot carry a cash-flow category")
        if not self.is_cash_account and category not in {
            "OPERATING",
            "INVESTING",
            "FINANCING",
        }:
            raise ValueError(
                "Non-cash accounts require OPERATING, INVESTING or FINANCING category"
            )
        self.cash_flow_category = category
        return self


class CashFlowAccountMappingResponse(CashFlowAccountMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    is_active: bool


class CashFlowStatementLine(BaseModel):
    category: str
    amount: Decimal
    entry_count: int


class CashFlowStatementResponse(BaseModel):
    start_date: date
    end_date: date
    opening_cash: Decimal
    operating_cash_flow: Decimal
    investing_cash_flow: Decimal
    financing_cash_flow: Decimal
    unclassified_cash_flow: Decimal
    net_cash_flow: Decimal
    closing_cash: Decimal
    computed_closing_cash: Decimal
    is_reconciled: bool
    is_complete: bool
    unclassified_entry_numbers: list[str]
    lines: list[CashFlowStatementLine]
