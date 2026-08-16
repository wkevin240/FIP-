from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.inventory.accounting import (
    InventoryAccountingProfileCreate,
    InventoryAccountingProfileResponse,
)
from app.schemas.inventory.stock import (
    StockAdjustmentCreate,
    StockBalanceResponse,
    StockIssueCreate,
    StockMovementResponse,
    StockReceiptCreate,
    StockTransferCreate,
    StockTransferResponse,
)
from app.services.inventory.inventory_accounting_service import (
    InventoryAccountingService,
)
from app.services.inventory.stock_service import StockService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> StockService:
    return StockService(session)


async def get_accounting_service(
    session: AsyncSession = Depends(get_db),
) -> InventoryAccountingService:
    return InventoryAccountingService(session)


@router.get("/accounting-profile", response_model=InventoryAccountingProfileResponse)
async def get_inventory_accounting_profile(
    service: InventoryAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:read")),
) -> InventoryAccountingProfileResponse:
    return await service.get_profile(tenant.organization_id)


@router.post(
    "/accounting-profile",
    response_model=InventoryAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_inventory_accounting_profile(
    data: InventoryAccountingProfileCreate,
    service: InventoryAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(
        require_permission("inventory_stock:accounting:configure")
    ),
) -> InventoryAccountingProfileResponse:
    return await service.configure_profile(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/receipts",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_stock_receipt(
    data: StockReceiptCreate,
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:receive")),
) -> StockMovementResponse:
    return await service.record_receipt(tenant.organization_id, data, tenant.user_id)


@router.post(
    "/issues", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED
)
async def record_stock_issue(
    data: StockIssueCreate,
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:issue")),
) -> StockMovementResponse:
    return await service.record_issue(tenant.organization_id, data, tenant.user_id)


@router.post(
    "/adjustments",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_stock_adjustment(
    data: StockAdjustmentCreate,
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:adjust")),
) -> StockMovementResponse:
    return await service.record_adjustment(tenant.organization_id, data, tenant.user_id)


@router.post(
    "/transfers",
    response_model=StockTransferResponse,
    status_code=status.HTTP_201_CREATED,
)
async def transfer_stock(
    data: StockTransferCreate,
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:transfer")),
) -> StockTransferResponse:
    transfer_id, source_movement, destination_movement = await service.transfer(
        tenant.organization_id, data
    )
    return StockTransferResponse(
        transfer_id=transfer_id,
        source_movement=source_movement,
        destination_movement=destination_movement,
    )


@router.get("/balances", response_model=list[StockBalanceResponse])
async def list_stock_balances(
    warehouse_id: str | None = Query(None),
    product_id: str | None = Query(None),
    below_reorder_point: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:read")),
) -> list[StockBalanceResponse]:
    return await service.list_balances(
        tenant.organization_id,
        warehouse_id,
        product_id,
        below_reorder_point,
        offset,
        limit,
    )


@router.get("/movements", response_model=list[StockMovementResponse])
async def list_stock_movements(
    warehouse_id: str | None = Query(None),
    product_id: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: StockService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("inventory_stock:read")),
) -> list[StockMovementResponse]:
    return await service.list_movements(
        tenant.organization_id,
        warehouse_id,
        product_id,
        start_date,
        end_date,
        offset,
        limit,
    )
