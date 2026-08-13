from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.payroll.configuration import PayrollPeriodCreate, PayrollPeriodResponse
from app.schemas.payroll.payroll import (
    PayrollAuditEventResponse,
    PayrollCorrectionCreate,
    PayrollCorrectionResponse,
    PayrollInputCreate,
    PayrollInputResponse,
    PayrollSlipResponse,
)
from app.services.payroll.payroll_service import PayrollService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> PayrollService:
    return PayrollService(session)


@router.post(
    "/periods",
    response_model=PayrollPeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_period(
    data: PayrollPeriodCreate,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:create")),
) -> PayrollPeriodResponse:
    return await service.create_period(tenant.organization_id, tenant.user_id, data)


@router.get("/periods", response_model=list[PayrollPeriodResponse])
async def list_periods(
    status_value: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:read")),
) -> list[PayrollPeriodResponse]:
    return await service.list_periods(
        tenant.organization_id, status_value, offset, limit
    )


@router.get("/periods/{payroll_period_id}", response_model=PayrollPeriodResponse)
async def get_period(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:read")),
) -> PayrollPeriodResponse:
    return await service.get_period(tenant.organization_id, payroll_period_id)


@router.post(
    "/periods/{payroll_period_id}/inputs",
    response_model=PayrollInputResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_input(
    payroll_period_id: str,
    data: PayrollInputCreate,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:calculate")),
) -> PayrollInputResponse:
    return await service.create_input(
        tenant.organization_id, tenant.user_id, payroll_period_id, data
    )


@router.post(
    "/periods/{payroll_period_id}/calculate", response_model=PayrollPeriodResponse
)
async def calculate_period(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:calculate")),
) -> PayrollPeriodResponse:
    return await service.calculate_period(
        tenant.organization_id, tenant.user_id, payroll_period_id
    )


@router.post(
    "/periods/{payroll_period_id}/validate", response_model=PayrollPeriodResponse
)
async def validate_period(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:validate")),
) -> PayrollPeriodResponse:
    return await service.validate_period(
        tenant.organization_id, tenant.user_id, payroll_period_id
    )


@router.post("/periods/{payroll_period_id}/lock", response_model=PayrollPeriodResponse)
async def lock_period(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:lock")),
) -> PayrollPeriodResponse:
    return await service.lock_period(
        tenant.organization_id, tenant.user_id, payroll_period_id
    )


@router.post("/periods/{payroll_period_id}/post", response_model=PayrollPeriodResponse)
async def post_period(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_period:post")),
) -> PayrollPeriodResponse:
    return await service.post_period(
        tenant.organization_id, tenant.user_id, payroll_period_id
    )


@router.get(
    "/periods/{payroll_period_id}/slips", response_model=list[PayrollSlipResponse]
)
async def list_slips(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_slip:read")),
) -> list[PayrollSlipResponse]:
    return await service.list_slips(tenant.organization_id, payroll_period_id)


@router.get(
    "/periods/{payroll_period_id}/audit-events",
    response_model=list[PayrollAuditEventResponse],
)
async def list_audit_events(
    payroll_period_id: str,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_audit:read")),
) -> list[PayrollAuditEventResponse]:
    return await service.list_audit_events(tenant.organization_id, payroll_period_id)


@router.post(
    "/slips/{payroll_slip_id}/corrections",
    response_model=PayrollCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_correction(
    payroll_slip_id: str,
    data: PayrollCorrectionCreate,
    service: PayrollService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_correction:create")),
) -> PayrollCorrectionResponse:
    return await service.request_correction(
        tenant.organization_id, tenant.user_id, payroll_slip_id, data
    )
