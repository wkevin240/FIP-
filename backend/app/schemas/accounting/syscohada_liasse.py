from datetime import date
from enum import StrEnum

from app.schemas.accounting.cash_flow import CashFlowStatementResponse
from app.schemas.accounting.professional_reporting import (
    ProfessionalFinancialStatementResponse,
    ProfessionalTrialBalanceResponse,
    ReportingReconciliationResponse,
)
from pydantic import BaseModel, Field


class LiasseReadinessStatus(StrEnum):
    NOT_READY = "NOT_READY"
    INCOMPLETE = "INCOMPLETE"
    READY = "READY"


class LiasseReadinessResponse(BaseModel):
    status: LiasseReadinessStatus
    reasons: list[str] = Field(default_factory=list)
    posted_entry_count: int = Field(ge=0)


class AnnexNoteResponse(BaseModel):
    code: str
    title: str
    status: LiasseReadinessStatus
    data: dict[str, object]


class SyscohadaLiasseResponse(BaseModel):
    framework: str = "SYSCOHADA"
    start_date: date
    end_date: date
    readiness: LiasseReadinessResponse
    reconciliation: ReportingReconciliationResponse | None = None
    professional_trial_balance: ProfessionalTrialBalanceResponse | None = None
    balance_sheet: ProfessionalFinancialStatementResponse | None = None
    income_statement: ProfessionalFinancialStatementResponse | None = None
    cash_flow: CashFlowStatementResponse | None = None
    annex_notes: list[AnnexNoteResponse] = Field(default_factory=list)
