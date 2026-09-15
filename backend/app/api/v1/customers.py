from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.core.validation import validate_pagination
from app.db.session import get_db
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter()


def get_customer_service(db: AsyncSession = Depends(get_db)) -> CustomerService:
    return CustomerService(db)


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_in: CustomerCreate,
    tenant: CurrentTenant = Depends(require_permission("customer:create")),
    service: CustomerService = Depends(get_customer_service),
):
    return await service.create(tenant.organization_id, tenant.user_id, customer_in)


@router.get("/", response_model=list[CustomerResponse])
async def read_customers(
    skip: int = 0,
    limit: int = 100,
    is_active: bool | None = None,
    tenant: CurrentTenant = Depends(require_permission("customer:read")),
    service: CustomerService = Depends(get_customer_service),
):
    skip, limit = validate_pagination(skip, limit)
    return await service.list(
        tenant.organization_id,
        skip=skip,
        limit=limit,
        is_active=is_active,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def read_customer(
    customer_id: str,
    tenant: CurrentTenant = Depends(require_permission("customer:read")),
    service: CustomerService = Depends(get_customer_service),
):
    return await service.get(tenant.organization_id, customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    customer_in: CustomerUpdate,
    tenant: CurrentTenant = Depends(require_permission("customer:update")),
    service: CustomerService = Depends(get_customer_service),
):
    return await service.update(tenant.organization_id, customer_id, tenant.user_id, customer_in)
