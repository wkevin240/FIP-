from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BankStatementImportLineResponse(BaseModel):
    id: str
    organization_id: str
    statement_import_id: str
    line_number: int
    external_id: str
    bank_transaction_id: str
    row_hash: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankStatementImportResponse(BaseModel):
    id: str
    organization_id: str
    treasury_bank_account_id: str
    imported_by_user_id: str
    idempotency_key: str
    content_hash: str
    source_filename: str
    format_version: str
    row_count: int
    imported_count: int
    duplicate_count: int
    status: str
    lines: list[BankStatementImportLineResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
