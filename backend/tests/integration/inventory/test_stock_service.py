from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.inventory import StockMovementType, StockUnit
from app.models.organization import Organization
from app.schemas.inventory.product import ProductCreate, ProductUpdate
from app.schemas.inventory.stock import (
    StockIssueCreate,
    StockReceiptCreate,
    StockTransferCreate,
)
from app.schemas.inventory.warehouse import WarehouseCreate
from app.services.inventory.product_service import ProductService
from app.services.inventory.stock_service import StockService
from app.services.inventory.warehouse_service import WarehouseService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_inventory_context(
    session: AsyncSession,
) -> tuple[Organization, str, str, str]:
    organization = Organization(name="Inventory test organization")
    session.add(organization)
    await session.commit()

    product = await ProductService(session).create_product(
        organization.id,
        ProductCreate(
            sku="sku-001",
            name="Stocked product",
            unit=StockUnit.UNIT,
            reorder_point=Decimal("10.000"),
        ),
    )
    warehouse_service = WarehouseService(session)
    source = await warehouse_service.create_warehouse(
        organization.id,
        WarehouseCreate(code="MAIN", name="Main warehouse"),
    )
    destination = await warehouse_service.create_warehouse(
        organization.id,
        WarehouseCreate(code="OUTLET", name="Outlet warehouse"),
    )
    return organization, product.id, source.id, destination.id


@pytest.mark.asyncio
async def test_receipt_issue_and_transfer_keep_valued_balances_consistent(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        product_id,
        source_id,
        destination_id,
    ) = await _create_inventory_context(db_session)
    service = StockService(db_session)

    first_receipt = await service.record_receipt(
        organization.id,
        StockReceiptCreate(
            warehouse_id=source_id,
            product_id=product_id,
            movement_date=date(2026, 1, 5),
            quantity=Decimal("10.000"),
            unit_cost=Decimal("10.0000"),
            reference="GRN-001",
        ),
    )
    second_receipt = await service.record_receipt(
        organization.id,
        StockReceiptCreate(
            warehouse_id=source_id,
            product_id=product_id,
            movement_date=date(2026, 1, 6),
            quantity=Decimal("5.000"),
            unit_cost=Decimal("16.0000"),
            reference="GRN-002",
        ),
    )
    issue = await service.record_issue(
        organization.id,
        StockIssueCreate(
            warehouse_id=source_id,
            product_id=product_id,
            movement_date=date(2026, 1, 7),
            quantity=Decimal("3.000"),
            reference="SO-001",
        ),
    )
    transfer_id, transfer_out, transfer_in = await service.transfer(
        organization.id,
        StockTransferCreate(
            source_warehouse_id=source_id,
            destination_warehouse_id=destination_id,
            product_id=product_id,
            movement_date=date(2026, 1, 8),
            quantity=Decimal("2.000"),
            reference="TR-001",
        ),
    )
    balances = await service.list_balances(organization.id)
    balances_by_warehouse = {balance.warehouse_id: balance for balance in balances}

    assert first_receipt.movement_type == StockMovementType.RECEIPT
    assert first_receipt.total_value == Decimal("100.00")
    assert second_receipt.total_value == Decimal("80.00")
    assert issue.movement_type == StockMovementType.ISSUE
    assert issue.unit_cost == Decimal("12.0000")
    assert issue.total_value == Decimal("36.00")
    assert transfer_out.movement_type == StockMovementType.TRANSFER_OUT
    assert transfer_in.movement_type == StockMovementType.TRANSFER_IN
    assert transfer_out.transfer_id == transfer_id == transfer_in.transfer_id
    assert transfer_out.total_value == Decimal("24.00")
    assert balances_by_warehouse[source_id].quantity == Decimal("10.000")
    assert balances_by_warehouse[source_id].total_value == Decimal("120.00")
    assert balances_by_warehouse[source_id].average_unit_cost == Decimal("12.0000")
    assert balances_by_warehouse[destination_id].quantity == Decimal("2.000")
    assert balances_by_warehouse[destination_id].total_value == Decimal("24.00")
    assert balances_by_warehouse[destination_id].average_unit_cost == Decimal("12.0000")


@pytest.mark.asyncio
async def test_rejects_issue_exceeding_available_stock_and_same_warehouse_transfer(
    db_session: AsyncSession,
) -> None:
    organization, product_id, source_id, _ = await _create_inventory_context(db_session)
    service = StockService(db_session)
    await service.record_receipt(
        organization.id,
        StockReceiptCreate(
            warehouse_id=source_id,
            product_id=product_id,
            movement_date=date(2026, 1, 5),
            quantity=Decimal("1.000"),
            unit_cost=Decimal("4.0000"),
        ),
    )

    with pytest.raises(HTTPException, match="Insufficient stock") as insufficient:
        await service.record_issue(
            organization.id,
            StockIssueCreate(
                warehouse_id=source_id,
                product_id=product_id,
                movement_date=date(2026, 1, 6),
                quantity=Decimal("1.001"),
            ),
        )
    assert insufficient.value.status_code == 422
    await db_session.refresh(organization, attribute_names=["id"])

    with pytest.raises(HTTPException, match="must differ") as same_warehouse:
        await service.transfer(
            organization.id,
            StockTransferCreate(
                source_warehouse_id=source_id,
                destination_warehouse_id=source_id,
                product_id=product_id,
                movement_date=date(2026, 1, 6),
                quantity=Decimal("1.000"),
            ),
        )
    assert same_warehouse.value.status_code == 422


@pytest.mark.asyncio
async def test_reorder_filter_and_inactive_product_rejection(
    db_session: AsyncSession,
) -> None:
    organization, product_id, source_id, _ = await _create_inventory_context(db_session)
    stock_service = StockService(db_session)
    await stock_service.record_receipt(
        organization.id,
        StockReceiptCreate(
            warehouse_id=source_id,
            product_id=product_id,
            movement_date=date(2026, 1, 5),
            quantity=Decimal("5.000"),
            unit_cost=Decimal("3.0000"),
        ),
    )

    below_reorder = await stock_service.list_balances(
        organization.id, below_reorder_point=True
    )
    await ProductService(db_session).update_product(
        organization.id, product_id, ProductUpdate(is_active=False)
    )

    assert [balance.product_id for balance in below_reorder] == [product_id]
    with pytest.raises(HTTPException, match="Active product") as inactive_product:
        await stock_service.record_receipt(
            organization.id,
            StockReceiptCreate(
                warehouse_id=source_id,
                product_id=product_id,
                movement_date=date(2026, 1, 6),
                quantity=Decimal("1.000"),
                unit_cost=Decimal("3.0000"),
            ),
        )
    assert inactive_product.value.status_code == 422


@pytest.mark.asyncio
async def test_product_sku_and_warehouse_code_are_unique_per_organization(
    db_session: AsyncSession,
) -> None:
    organization, _, _, _ = await _create_inventory_context(db_session)

    with pytest.raises(HTTPException, match="SKU already exists") as duplicate_sku:
        await ProductService(db_session).create_product(
            organization.id,
            ProductCreate(sku="SKU-001", name="Duplicate product"),
        )
    assert duplicate_sku.value.status_code == 409

    with pytest.raises(HTTPException, match="code already exists") as duplicate_code:
        await WarehouseService(db_session).create_warehouse(
            organization.id,
            WarehouseCreate(code="main", name="Duplicate warehouse"),
        )
    assert duplicate_code.value.status_code == 409
