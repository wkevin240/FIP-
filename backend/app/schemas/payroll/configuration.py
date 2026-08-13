from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContributionRuleCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    direction: str = Field(..., pattern="^(EMPLOYEE|EMPLOYER)$")
    base_type: str = Field(default="GROSS", pattern="^(GROSS|TAXABLE_GROSS)$")
    rate: Decimal = Field(..., ge=0, le=100, decimal_places=6)
    cap_amount: Decimal | None = Field(None, ge=0, decimal_places=2)
    sort_order: int = Field(..., ge=1)


class ContributionRuleResponse(ContributionRuleCreate):
    id: str
    rule_set_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TaxBracketCreate(BaseModel):
    lower_bound: Decimal = Field(..., ge=0, decimal_places=2)
    upper_bound: Decimal | None = Field(None, gt=0, decimal_places=2)
    rate: Decimal = Field(..., ge=0, le=100, decimal_places=6)
    sort_order: int = Field(..., ge=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "TaxBracketCreate":
        if self.upper_bound is not None and self.upper_bound <= self.lower_bound:
            raise ValueError("Tax bracket upper bound must exceed lower bound")
        return self


class TaxBracketResponse(TaxBracketCreate):
    id: str
    rule_set_id: str

    model_config = ConfigDict(from_attributes=True)


class PayrollRuleSetCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    effective_from: date
    effective_to: date | None = None
    currency: str = Field(default="XAF", min_length=3, max_length=3)
    professional_expense_rate: Decimal = Field(
        default=Decimal("0.000000"), ge=0, le=100
    )
    professional_expense_cap: Decimal | None = Field(None, ge=0, decimal_places=2)
    annual_tax_allowance: Decimal = Field(
        default=Decimal("0.00"), ge=0, decimal_places=2
    )
    local_surtax_rate: Decimal = Field(default=Decimal("0.000000"), ge=0, le=100)
    source_reference: str | None = Field(None, max_length=500)
    notes: str | None = None
    contribution_rules: list[ContributionRuleCreate] = Field(default_factory=list)
    tax_brackets: list[TaxBracketCreate] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_effectivity_and_brackets(self) -> "PayrollRuleSetCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Rule set effective end cannot precede its start")
        bracket_orders = [bracket.sort_order for bracket in self.tax_brackets]
        if len(bracket_orders) != len(set(bracket_orders)):
            raise ValueError("Tax bracket sort orders must be unique")
        contribution_orders = [rule.sort_order for rule in self.contribution_rules]
        if len(contribution_orders) != len(set(contribution_orders)):
            raise ValueError("Contribution rule sort orders must be unique")
        return self


class PayrollRuleSetResponse(BaseModel):
    id: str
    organization_id: str
    code: str
    name: str
    effective_from: date
    effective_to: date | None
    currency: str
    professional_expense_rate: Decimal
    professional_expense_cap: Decimal | None
    annual_tax_allowance: Decimal
    local_surtax_rate: Decimal
    is_active: bool
    source_reference: str | None
    notes: str | None
    contribution_rules: list[ContributionRuleResponse]
    tax_brackets: list[TaxBracketResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollAccountingProfileCreate(BaseModel):
    profile_code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    journal_id: str
    salary_expense_account_id: str
    employer_charge_account_id: str
    employee_payable_account_id: str
    tax_payable_account_id: str
    social_payable_account_id: str
    other_deduction_payable_account_id: str


class PayrollAccountingProfileResponse(PayrollAccountingProfileCreate):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PayrollPeriodCreate(BaseModel):
    period_code: str = Field(..., min_length=1, max_length=64)
    start_date: date
    end_date: date
    payment_date: date
    fiscal_period_id: str
    rule_set_id: str
    accounting_profile_id: str
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "PayrollPeriodCreate":
        if self.end_date < self.start_date:
            raise ValueError("Payroll period end cannot precede start")
        if self.payment_date < self.start_date:
            raise ValueError("Payroll payment date cannot precede start")
        return self


class PayrollPeriodResponse(BaseModel):
    id: str
    organization_id: str
    period_code: str
    start_date: date
    end_date: date
    payment_date: date
    fiscal_period_id: str
    rule_set_id: str
    accounting_profile_id: str
    status: str
    gross_total: Decimal
    employee_contribution_total: Decimal
    employer_contribution_total: Decimal
    tax_total: Decimal
    other_deduction_total: Decimal
    net_total: Decimal
    journal_entry_id: str | None
    calculated_at: datetime | None
    validated_at: datetime | None
    locked_at: datetime | None
    posted_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
