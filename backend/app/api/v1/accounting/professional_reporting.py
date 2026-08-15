from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.professional_reporting import (
    FinancialStatementMappingCreate,
    FinancialStatementMappingResponse,
    ProfessionalFinancialStatementResponse,
    ProfessionalTrialBalanceResponse,
    ReportingReconciliationResponse,
)
from app.services.accounting.financial_statement_mapping_service import (
    FinancialStatementMappingService,
)
from app.services.accounting.reporting_service import ReportingService
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_reporting_service(
    session: AsyncSession = Depends(get_db),
) -> ReportingService:
    return ReportingService(session)


async def get_mapping_service(
    session: AsyncSession = Depends(get_db),
) -> FinancialStatementMappingService:
    return FinancialStatementMappingService(session)


@router.post(
    "/mappings",
    response_model=FinancialStatementMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    data: FinancialStatementMappingCreate,
    service: FinancialStatementMappingService = Depends(get_mapping_service),
    tenant: CurrentTenant = Depends(
        require_permission("professional_reporting:configure")
    ),
) -> FinancialStatementMappingResponse:
    return await service.create(tenant.organization_id, tenant.user_id, data)


@router.get("/mappings", response_model=list[FinancialStatementMappingResponse])
async def list_mappings(
    statement_code: str = Query(..., pattern="^(BALANCE_SHEET|INCOME_STATEMENT)$"),
    framework: str = Query("SYSCOHADA", pattern="^SYSCOHADA$"),
    service: FinancialStatementMappingService = Depends(get_mapping_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> list[FinancialStatementMappingResponse]:
    return await service.list_active(tenant.organization_id, framework, statement_code)


@router.get("/trial-balance", response_model=ProfessionalTrialBalanceResponse)
async def get_professional_trial_balance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: ReportingService = Depends(get_reporting_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> ProfessionalTrialBalanceResponse:
    return await service.professional_trial_balance(
        tenant.organization_id, start_date, end_date
    )


@router.get("/trial-balance/export.csv", response_class=Response)
async def export_professional_trial_balance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: ReportingService = Depends(get_reporting_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> Response:
    content = await service.export_professional_trial_balance_csv(
        tenant.organization_id, tenant.user_id, start_date, end_date
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=professional-trial-balance.csv"
            )
        },
    )


@router.get(
    "/statements/{statement_code}",
    response_model=ProfessionalFinancialStatementResponse,
)
async def get_professional_financial_statement(
    statement_code: str,
    end_date: date = Query(...),
    start_date: date | None = Query(None),
    framework: str = Query("SYSCOHADA", pattern="^SYSCOHADA$"),
    service: ReportingService = Depends(get_reporting_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> ProfessionalFinancialStatementResponse:
    return await service.professional_financial_statement(
        tenant.organization_id, statement_code, end_date, start_date, framework
    )


@router.get("/reconciliation", response_model=ReportingReconciliationResponse)
async def get_reporting_reconciliation(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: ReportingService = Depends(get_reporting_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> ReportingReconciliationResponse:
    return await service.reconcile_reporting(
        tenant.organization_id, start_date, end_date
    )
