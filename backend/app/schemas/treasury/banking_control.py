from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BankingControlRefreshResponse(BaseModel):
    statement_import_id: str
    total_imported: int = Field(ge=0)
    RECONCILED: int = Field(ge=0)
    NO_MATCH: int = Field(ge=0)
    AMBIGUOUS: int = Field(ge=0)
    PENDING: int = Field(ge=0)
    REJECTED: int = Field(ge=0)
    INVALID_RULE: int = Field(ge=0)
    POSTED_UNRECONCILED: int = Field(ge=0)


class BankingControlExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bank_transaction_id: str
    statement_import_id: str | None
    status: str
    reason: str
    last_seen_at: datetime
    resolved_at: datetime | None


class BankStatementClosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    statement_import_id: str
    closed_by_user_id: str
    closed_at: datetime
    imported_count: int
    reconciled_count: int
    unresolved_count: int
