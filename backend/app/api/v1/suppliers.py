from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.core.validation import validate_pagination
from app.db.session import get_db
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate
from app.services.supplier_service import SupplierService

router = APIRouter()


def get_supplier_service(db: AsyncSession = Depends(get_db)) -> SupplierService:
    return SupplierService(db)


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_in: SupplierCreate,
    tenant: CurrentTenant = Depends(require_permission("supplier:create")),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.create(tenant.organization_id, tenant.user_id, supplier_in)


@router.get("/", response_model=list[SupplierResponse])
async def read_suppliers(
    skip: int = 0,
    limit: int = 100,
    is_active: bool | None = None,
    tenant: CurrentTenant = Depends(require_permission("supplier:read")),
    service: SupplierService = Depends(get_supplier_service),
):
    skip, limit = validate_pagination(skip, limit)
    return await service.list(tenant.organization_id, skip=skip, limit=limit, is_active=is_active)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def read_supplier(
    supplier_id: str,
    tenant: CurrentTenant = Depends(require_permission("supplier:read")),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.get(tenant.organization_id, supplier_id)


@router.patch("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    supplier_in: SupplierUpdate,
    tenant: CurrentTenant = Depends(require_permission("supplier:update")),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.update(tenant.organization_id, supplier_id, tenant.user_id, supplier_in)
