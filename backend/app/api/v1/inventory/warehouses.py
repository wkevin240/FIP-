from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.inventory.warehouse import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.services.inventory.warehouse_service import WarehouseService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> WarehouseService:
    return WarehouseService(session)


@router.post("/", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    data: WarehouseCreate,
    service: WarehouseService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_warehouse:create")),
) -> WarehouseResponse:
    return await service.create_warehouse(tenant.organization_id, data)


@router.get("/", response_model=list[WarehouseResponse])
async def list_warehouses(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: bool = Query(False),
    service: WarehouseService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_warehouse:read")),
) -> list[WarehouseResponse]:
    return await service.list_warehouses(
        tenant.organization_id, offset, limit, active_only
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: str,
    service: WarehouseService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_warehouse:read")),
) -> WarehouseResponse:
    return await service.get_warehouse(tenant.organization_id, warehouse_id)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: str,
    data: WarehouseUpdate,
    service: WarehouseService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_warehouse:update")),
) -> WarehouseResponse:
    return await service.update_warehouse(tenant.organization_id, warehouse_id, data)
