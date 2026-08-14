from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FinancialStatementMappingCreate(BaseModel):
    account_id: str
    framework: str = Field(default="SYSCOHADA", max_length=32)
    statement_code: str = Field(..., pattern="^(BALANCE_SHEET|INCOME_STATEMENT)$")
    presentation_role: str = Field(..., min_length=1, max_length=32)
    section_code: str = Field(..., min_length=1, max_length=64)
    section_label: str = Field(..., min_length=1, max_length=255)
    line_code: str = Field(..., min_length=1, max_length=64)
    line_label: str = Field(..., min_length=1, max_length=255)
    display_order: int = Field(default=0, ge=0)

    @field_validator("framework")
    @classmethod
    def validate_framework(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "SYSCOHADA":
            raise ValueError("Only SYSCOHADA mappings are supported")
        return normalized

    @field_validator("presentation_role")
    @classmethod
    def validate_presentation_role(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {
            "ASSETS",
            "LIABILITIES_EQUITY",
            "REVENUE",
            "EXPENSE",
        }:
            raise ValueError("Unsupported presentation role")
        return normalized


class FinancialStatementMappingResponse(FinancialStatementMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    is_active: bool


class ProfessionalTrialBalanceLine(BaseModel):
    account_id: str
    code: str
    name: str
    account_type: str
    opening_debit: Decimal
    opening_credit: Decimal
    movement_debit: Decimal
    movement_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal


class ProfessionalTrialBalanceResponse(BaseModel):
    start_date: date
    end_date: date
    lines: list[ProfessionalTrialBalanceLine]
    total_opening_debit: Decimal
    total_opening_credit: Decimal
    total_movement_debit: Decimal
    total_movement_credit: Decimal
    total_closing_debit: Decimal
    total_closing_credit: Decimal
    is_opening_balanced: bool
    is_movement_balanced: bool
    is_closing_balanced: bool


class ProfessionalFinancialStatementLine(BaseModel):
    presentation_role: str
    section_code: str
    section_label: str
    line_code: str
    line_label: str
    display_order: int
    balance: Decimal


class ProfessionalFinancialStatementResponse(BaseModel):
    framework: str
    statement_code: str
    start_date: date | None = None
    end_date: date
    lines: list[ProfessionalFinancialStatementLine]
    total: Decimal
    total_assets: Decimal | None = None
    total_liabilities_and_equity: Decimal | None = None
    net_result: Decimal | None = None
    is_balanced: bool | None = None
    unmapped_account_codes: list[str]


class ReportingReconciliationResponse(BaseModel):
    start_date: date
    end_date: date
    trial_balance_is_balanced: bool
    balance_sheet_is_balanced: bool
    professional_balance_sheet_is_balanced: bool
    professional_balance_sheet_is_complete: bool
    unmapped_balance_sheet_account_codes: list[str]
    movement_debit: Decimal
    movement_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
    is_consistent: bool
