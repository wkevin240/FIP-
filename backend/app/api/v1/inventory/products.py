from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.inventory.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.inventory.product_service import ProductService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ProductService:
    return ProductService(session)


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_product:create")),
) -> ProductResponse:
    return await service.create_product(tenant.organization_id, data)


@router.get("/", response_model=list[ProductResponse])
async def list_products(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: bool = Query(False),
    service: ProductService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_product:read")),
) -> list[ProductResponse]:
    return await service.list_products(
        tenant.organization_id, offset, limit, active_only
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_product:read")),
) -> ProductResponse:
    return await service.get_product(tenant.organization_id, product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    service: ProductService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_product:update")),
) -> ProductResponse:
    return await service.update_product(tenant.organization_id, product_id, data)
