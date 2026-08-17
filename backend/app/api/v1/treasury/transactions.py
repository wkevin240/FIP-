from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.accounting import (
    TreasuryAccountingPostingResponse,
    TreasuryAccountingProfileCreate,
    TreasuryAccountingProfileResponse,
    TreasuryTransactionPostingCreate,
)
from app.schemas.treasury.bank_statement_import import BankStatementImportResponse
from app.schemas.treasury.reconciliation import TreasuryReconciliationCandidate
from app.schemas.treasury.transaction import (
    TreasuryBankTransactionCreate,
    TreasuryBankTransactionResponse,
)
from app.services.treasury.bank_statement_import_service import (
    BankStatementImportService,
)
from app.services.treasury.transaction_service import TreasuryTransactionService
from app.services.treasury.treasury_accounting_service import TreasuryAccountingService
from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryTransactionService:
    return TreasuryTransactionService(session)


async def get_accounting_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryAccountingService:
    return TreasuryAccountingService(session)


async def get_import_service(
    session: AsyncSession = Depends(get_db),
) -> BankStatementImportService:
    return BankStatementImportService(session)


@router.post(
    "/imports/csv",
    response_model=BankStatementImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_bank_statement_csv(
    treasury_bank_account_id: str = Form(...),
    statement_file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    service: BankStatementImportService = Depends(get_import_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:create")),
) -> BankStatementImportResponse:
    filename = statement_file.filename or "bank-statement.csv"
    return await service.import_csv(
        tenant.organization_id,
        tenant.user_id,
        treasury_bank_account_id,
        idempotency_key,
        filename,
        await statement_file.read(),
    )


@router.post(
    "/imports/ofx",
    response_model=BankStatementImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_bank_statement_ofx(
    treasury_bank_account_id: str = Form(...),
    statement_file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    service: BankStatementImportService = Depends(get_import_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:create")),
) -> BankStatementImportResponse:
    filename = statement_file.filename or "bank-statement.ofx"
    return await service.import_ofx(
        tenant.organization_id,
        tenant.user_id,
        treasury_bank_account_id,
        idempotency_key,
        filename,
        await statement_file.read(),
    )


@router.get("/accounting-profile", response_model=TreasuryAccountingProfileResponse)
async def get_treasury_accounting_profile(
    service: TreasuryAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:read")),
) -> TreasuryAccountingProfileResponse:
    return await service.get_profile(tenant.organization_id)


@router.post(
    "/accounting-profile",
    response_model=TreasuryAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_treasury_accounting_profile(
    data: TreasuryAccountingProfileCreate,
    service: TreasuryAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(
        require_permission("treasury_accounting:configure")
    ),
) -> TreasuryAccountingProfileResponse:
    return await service.configure_profile(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/{transaction_id}/post-accounting",
    response_model=TreasuryAccountingPostingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_treasury_transaction(
    transaction_id: str,
    data: TreasuryTransactionPostingCreate,
    service: TreasuryAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:post")),
) -> TreasuryAccountingPostingResponse:
    return await service.post_transaction(
        tenant.organization_id, tenant.user_id, transaction_id, data
    )


@router.post(
    "/",
    response_model=TreasuryBankTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: TreasuryBankTransactionCreate,
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:create")),
) -> TreasuryBankTransactionResponse:
    return await service.create_transaction(tenant.organization_id, data)


@router.get(
    "/bank-accounts/{treasury_bank_account_id}",
    response_model=list[TreasuryBankTransactionResponse],
)
async def list_transactions(
    treasury_bank_account_id: str,
    reconciled: bool | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:read")),
) -> list[TreasuryBankTransactionResponse]:
    return await service.list_transactions(
        tenant.organization_id,
        treasury_bank_account_id,
        reconciled,
        offset,
        limit,
    )


@router.get(
    "/bank-accounts/{treasury_bank_account_id}/{transaction_id}/candidates",
    response_model=list[TreasuryReconciliationCandidate],
)
async def candidate_entries(
    treasury_bank_account_id: str,
    transaction_id: str,
    date_window_days: int = Query(7, ge=0, le=90),
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_reconciliation:read")),
) -> list[TreasuryReconciliationCandidate]:
    return await service.candidate_entries(
        tenant.organization_id,
        treasury_bank_account_id,
        transaction_id,
        date_window_days,
    )
