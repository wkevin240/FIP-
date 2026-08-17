from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.core.enums.inventory import StockUnit
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal import Journal
from app.models.accounting.journal_entry import JournalEntry
from app.models.inventory.accounting import InventoryAccountingPosting
from app.models.organization import Organization
from app.schemas.inventory.accounting import InventoryAccountingProfileCreate
from app.schemas.inventory.product import ProductCreate
from app.schemas.inventory.stock import StockReceiptCreate
from app.schemas.inventory.warehouse import WarehouseCreate
from app.services.inventory.inventory_accounting_service import (
    InventoryAccountingService,
)
from app.services.inventory.product_service import ProductService
from app.services.inventory.stock_service import StockService
from app.services.inventory.warehouse_service import WarehouseService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_receipt_posts_balanced_inventory_entry_atomically(
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:10]
    organization = Organization(name=f"Inventory accounting {suffix}")
    db_session.add(organization)
    await db_session.flush()
    year = FiscalYear(
        organization_id=organization.id,
        name=f"FY {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    db_session.add(year)
    await db_session.flush()
    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=year.id,
        name=f"P {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    journal = Journal(
        organization_id=organization.id,
        code=f"ST{suffix[:8]}",
        name="Stock journal",
        journal_type="GENERAL",
        is_active=True,
    )
    accounts = [
        Account(
            organization_id=organization.id,
            code=f"31{suffix[:7]}",
            name="Inventory",
            account_type="ASSET",
            level=1,
            path="/31/",
        ),
        Account(
            organization_id=organization.id,
            code=f"40{suffix[:7]}",
            name="Receipt",
            account_type="LIABILITY",
            level=1,
            path="/40/",
        ),
        Account(
            organization_id=organization.id,
            code=f"60{suffix[:7]}",
            name="COGS",
            account_type="EXPENSE",
            level=1,
            path="/60/",
        ),
        Account(
            organization_id=organization.id,
            code=f"70{suffix[:7]}",
            name="Gain",
            account_type="REVENUE",
            level=1,
            path="/70/",
        ),
        Account(
            organization_id=organization.id,
            code=f"65{suffix[:7]}",
            name="Loss",
            account_type="EXPENSE",
            level=1,
            path="/65/",
        ),
    ]
    db_session.add_all([period, journal, *accounts])
    await db_session.commit()
    product = await ProductService(db_session).create_product(
        organization.id,
        ProductCreate(sku=f"SKU-{suffix}", name="Stock item", unit=StockUnit.UNIT),
    )
    warehouse = await WarehouseService(db_session).create_warehouse(
        organization.id, WarehouseCreate(code=f"WH{suffix[:8]}", name="Warehouse")
    )
    await InventoryAccountingService(db_session).configure_profile(
        organization.id,
        "tester",
        InventoryAccountingProfileCreate(
            journal_id=journal.id,
            inventory_account_id=accounts[0].id,
            receipt_counterpart_account_id=accounts[1].id,
            cost_of_sales_account_id=accounts[2].id,
            adjustment_gain_account_id=accounts[3].id,
            adjustment_loss_account_id=accounts[4].id,
        ),
    )
    movement = await StockService(db_session).record_receipt(
        organization.id,
        StockReceiptCreate(
            warehouse_id=warehouse.id,
            product_id=product.id,
            movement_date=date(2026, 2, 1),
            quantity=Decimal("2.000"),
            unit_cost=Decimal("12.5000"),
        ),
        "tester",
    )
    posting = await db_session.scalar(
        select(InventoryAccountingPosting).where(
            InventoryAccountingPosting.source_id == movement.id
        )
    )
    assert posting is not None
    entry = await db_session.get(JournalEntry, posting.journal_entry_id)
    assert entry is not None and entry.status.value == "POSTED"
    assert (
        await db_session.scalar(
            select(func.count(InventoryAccountingPosting.id)).where(
                InventoryAccountingPosting.source_id == movement.id
            )
        )
        == 1
    )
