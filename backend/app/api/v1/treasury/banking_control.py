from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.banking_control import (
    BankingControlExceptionResponse,
    BankingControlRefreshResponse,
    BankStatementClosureResponse,
)
from app.schemas.treasury.banking_cross_reconciliation import (
    BankingCrossReconciliationResponse,
)
from app.services.treasury.banking_control_service import BankingControlService
from app.services.treasury.banking_cross_reconciliation_service import (
    BankingCrossReconciliationService,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/cross-reconciliation",
    response_model=BankingCrossReconciliationResponse,
)
async def cross_reconciliation_report(
    as_of: date = Query(default_factory=date.today),
    tenant: CurrentTenant = Depends(require_permission("bank_control:read")),
    session: AsyncSession = Depends(get_db),
) -> BankingCrossReconciliationResponse:
    return await BankingCrossReconciliationService(session).report(
        tenant.organization_id, as_of
    )


async def get_service(session: AsyncSession = Depends(get_db)) -> BankingControlService:
    return BankingControlService(session)


@router.post(
    "/imports/{statement_import_id}/refresh",
    response_model=BankingControlRefreshResponse,
)
async def refresh_statement_control(
    statement_import_id: str,
    service: BankingControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_control:refresh")),
) -> BankingControlRefreshResponse:
    return await service.refresh_import(
        tenant.organization_id, tenant.user_id, statement_import_id
    )


@router.get(
    "/exceptions",
    response_model=list[BankingControlExceptionResponse],
)
async def list_statement_exceptions(
    statement_import_id: str | None = Query(default=None),
    exception_status: str | None = Query(default=None, alias="status"),
    unresolved_only: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: BankingControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_control:read")),
) -> list[BankingControlExceptionResponse]:
    return await service.list_exceptions(
        tenant.organization_id,
        statement_import_id=statement_import_id,
        exception_status=exception_status,
        unresolved_only=unresolved_only,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/imports/{statement_import_id}/close",
    response_model=BankStatementClosureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def close_statement(
    statement_import_id: str,
    service: BankingControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_control:close")),
) -> BankStatementClosureResponse:
    return await service.close_import(
        tenant.organization_id, tenant.user_id, statement_import_id
    )
