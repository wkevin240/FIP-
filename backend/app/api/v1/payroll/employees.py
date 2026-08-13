from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.payroll.employee import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    EmploymentContractCreate,
    EmploymentContractResponse,
    EmploymentContractUpdate,
)
from app.services.payroll.employee_service import EmployeeService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> EmployeeService:
    return EmployeeService(session)


@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_employee:create")),
) -> EmployeeResponse:
    return await service.create_employee(tenant.organization_id, tenant.user_id, data)


@router.get("/", response_model=list[EmployeeResponse])
async def list_employees(
    active_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_employee:read")),
) -> list[EmployeeResponse]:
    return await service.list_employees(
        tenant.organization_id, active_only, offset, limit
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_employee:read")),
) -> EmployeeResponse:
    return await service.get_employee(tenant.organization_id, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: str,
    data: EmployeeUpdate,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_employee:update")),
) -> EmployeeResponse:
    return await service.update_employee(
        tenant.organization_id, tenant.user_id, employee_id, data
    )


@router.post(
    "/{employee_id}/contracts",
    response_model=EmploymentContractResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contract(
    employee_id: str,
    data: EmploymentContractCreate,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_contract:create")),
) -> EmploymentContractResponse:
    return await service.create_contract(
        tenant.organization_id, tenant.user_id, employee_id, data
    )


@router.get("/{employee_id}/contracts", response_model=list[EmploymentContractResponse])
async def list_contracts(
    employee_id: str,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_contract:read")),
) -> list[EmploymentContractResponse]:
    return await service.list_contracts(tenant.organization_id, employee_id)


@router.patch("/contracts/{contract_id}", response_model=EmploymentContractResponse)
async def update_contract(
    contract_id: str,
    data: EmploymentContractUpdate,
    service: EmployeeService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_contract:update")),
) -> EmploymentContractResponse:
    return await service.update_contract(
        tenant.organization_id, tenant.user_id, contract_id, data
    )
