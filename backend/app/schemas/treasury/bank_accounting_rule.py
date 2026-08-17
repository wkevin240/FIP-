from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BankAccountingRuleCriteria(BaseModel):
    description_pattern: str | None = Field(default=None, min_length=1, max_length=256)
    reference_pattern: str | None = Field(default=None, min_length=1, max_length=256)
    amount_min: Decimal | None = Field(default=None, ge=Decimal(0))
    amount_max: Decimal | None = Field(default=None, ge=Decimal(0))
    direction: str | None = None

    @field_validator("description_pattern", "reference_pattern")
    @classmethod
    def normalize_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("A matching pattern cannot be blank")
        return normalized

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in {"CREDIT", "DEBIT"}:
            raise ValueError("Direction must be CREDIT or DEBIT")
        return normalized

    @model_validator(mode="after")
    def validate_criteria(self) -> "BankAccountingRuleCriteria":
        if not any(
            (
                self.description_pattern,
                self.reference_pattern,
                self.amount_min is not None,
                self.amount_max is not None,
                self.direction,
            )
        ):
            raise ValueError("At least one explicit matching criterion is required")
        if (
            self.amount_min is not None
            and self.amount_max is not None
            and self.amount_min > self.amount_max
        ):
            raise ValueError("amount_min cannot exceed amount_max")
        return self


class BankAccountingRuleCreate(BankAccountingRuleCriteria):
    name: str = Field(min_length=1, max_length=120)
    counterpart_account_id: str = Field(min_length=1)
    priority: int = Field(ge=0)
    category: str | None = Field(default=None, max_length=64)
    is_active: bool = True

    @field_validator("name", "category")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text fields cannot be blank")
        return normalized


class BankAccountingRuleUpdate(BankAccountingRuleCriteria):
    name: str = Field(min_length=1, max_length=120)
    counterpart_account_id: str = Field(min_length=1)
    priority: int = Field(ge=0)
    category: str | None = Field(default=None, max_length=64)
    is_active: bool

    @field_validator("name", "category")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text fields cannot be blank")
        return normalized


class BankAccountingRuleResponse(BankAccountingRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str


class BankAccountingProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    bank_transaction_id: str
    rule_id: str
    counterpart_account_id: str
    rule_name: str
    category: str | None
    rule_snapshot_hash: str
    status: str
    journal_entry_id: str | None
    decision_idempotency_key: str | None
    rejection_reason: str | None
    decided_by_user_id: str | None
    decided_at: datetime | None


class BankAccountingProposalPreview(BaseModel):
    bank_transaction_id: str
    outcome: str
    proposal: BankAccountingProposalResponse | None = None
    matching_rule_ids: list[str] = []


class BankAccountingProposalDecision(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Idempotency key cannot be blank")
        return normalized


class BankAccountingProposalRejection(BankAccountingProposalDecision):
    rejection_reason: str = Field(min_length=1, max_length=500)

    @field_validator("rejection_reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Rejection reason cannot be blank")
        return normalized
