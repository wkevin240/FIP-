from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.core.enums.inventory import StockMovementType
from app.domain.inventory.stock.rules import StockValuationRules, ValuedStockBalance
from app.models.inventory.product import Product
from app.models.inventory.stock_balance import StockBalance
from app.models.inventory.stock_movement import StockMovement
from app.models.inventory.warehouse import Warehouse
from app.repositories.inventory.product_repository import ProductRepository
from app.repositories.inventory.stock_balance_repository import StockBalanceRepository
from app.repositories.inventory.stock_movement_repository import StockMovementRepository
from app.repositories.inventory.warehouse_repository import WarehouseRepository
from app.schemas.inventory.stock import (
    StockAdjustmentCreate,
    StockIssueCreate,
    StockReceiptCreate,
    StockTransferCreate,
)
from app.services.inventory.inventory_accounting_service import (
    InventoryAccountingService,
)
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class StockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.warehouses = WarehouseRepository(session)
        self.balances = StockBalanceRepository(session)
        self.movements = StockMovementRepository(session)

    async def record_receipt(
        self,
        organization_id: str,
        data: StockReceiptCreate,
        actor_user_id: str | None = None,
    ) -> StockMovement:
        try:
            await self._validate_active_references(
                organization_id, data.product_id, data.warehouse_id
            )
            balance = await self._locked_or_new_balance(
                organization_id, data.warehouse_id, data.product_id
            )
            total_value = StockValuationRules.money(data.quantity * data.unit_cost)
            self._increase_balance(balance, data.quantity, total_value)
            movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.RECEIPT,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=data.unit_cost,
                total_value=total_value,
                transfer_id=None,
                reference=data.reference,
                note=data.note,
            )
            if actor_user_id is not None:
                await InventoryAccountingService(self.session).post_movement(
                    organization_id, actor_user_id, movement
                )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent stock update conflict",
            ) from exc
        await self.session.refresh(movement)
        return movement

    async def record_issue(
        self,
        organization_id: str,
        data: StockIssueCreate,
        actor_user_id: str | None = None,
    ) -> StockMovement:
        try:
            await self._validate_active_references(
                organization_id, data.product_id, data.warehouse_id
            )
            balance = await self.balances.get_for_update(
                organization_id, data.warehouse_id, data.product_id
            )
            unit_cost, total_value = self._decrease_balance(balance, data.quantity)
            movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.ISSUE,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=unit_cost,
                total_value=total_value,
                transfer_id=None,
                reference=data.reference,
                note=data.note,
            )
            if actor_user_id is not None:
                await InventoryAccountingService(self.session).post_movement(
                    organization_id, actor_user_id, movement
                )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        await self.session.refresh(movement)
        return movement

    async def record_adjustment(
        self,
        organization_id: str,
        data: StockAdjustmentCreate,
        actor_user_id: str | None = None,
    ) -> StockMovement:
        if data.direction == "IN":
            if data.unit_cost is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Unit cost is required for an inbound stock adjustment",
                )
            receipt = StockReceiptCreate(
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=data.unit_cost,
                reference=data.reference,
                note=data.note,
            )
            return await self._record_inbound_adjustment(
                organization_id, receipt, actor_user_id
            )
        if data.unit_cost is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unit cost is derived from average cost for an outbound adjustment",
            )
        issue = StockIssueCreate(
            warehouse_id=data.warehouse_id,
            product_id=data.product_id,
            movement_date=data.movement_date,
            quantity=data.quantity,
            reference=data.reference,
            note=data.note,
        )
        return await self._record_outbound_adjustment(
            organization_id, issue, actor_user_id
        )

    async def transfer(
        self, organization_id: str, data: StockTransferCreate
    ) -> tuple[str, StockMovement, StockMovement]:
        if data.source_warehouse_id == data.destination_warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Source and destination warehouses must differ",
            )
        try:
            await self._validate_active_references(
                organization_id, data.product_id, data.source_warehouse_id
            )
            await self._validate_active_references(
                organization_id, data.product_id, data.destination_warehouse_id
            )
            locked_balances: dict[str, StockBalance | None] = {}
            for warehouse_id in sorted(
                [data.source_warehouse_id, data.destination_warehouse_id]
            ):
                locked_balances[warehouse_id] = await self.balances.get_for_update(
                    organization_id, warehouse_id, data.product_id
                )
            source_balance = locked_balances[data.source_warehouse_id]
            destination_balance = locked_balances[data.destination_warehouse_id]
            if destination_balance is None:
                destination_balance = await self.balances.create(
                    organization_id,
                    data.destination_warehouse_id,
                    data.product_id,
                )
            unit_cost, total_value = self._decrease_balance(
                source_balance, data.quantity
            )
            self._increase_balance(destination_balance, data.quantity, total_value)
            transfer_id = str(uuid4())
            source_movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.source_warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.TRANSFER_OUT,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=unit_cost,
                total_value=total_value,
                transfer_id=transfer_id,
                reference=data.reference,
                note=data.note,
            )
            destination_movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.destination_warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.TRANSFER_IN,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=unit_cost,
                total_value=total_value,
                transfer_id=transfer_id,
                reference=data.reference,
                note=data.note,
            )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent stock transfer conflict",
            ) from exc
        await self.session.refresh(source_movement)
        await self.session.refresh(destination_movement)
        return transfer_id, source_movement, destination_movement

    async def list_balances(
        self,
        organization_id: str,
        warehouse_id: str | None = None,
        product_id: str | None = None,
        below_reorder_point: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[StockBalance]:
        return await self.balances.list(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            below_reorder_point=below_reorder_point,
            offset=max(offset, 0),
            limit=min(max(limit, 1), 100),
        )

    async def list_movements(
        self,
        organization_id: str,
        warehouse_id: str | None = None,
        product_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[StockMovement]:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )
        return await self.movements.list(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            offset=max(offset, 0),
            limit=min(max(limit, 1), 100),
        )

    async def _record_inbound_adjustment(
        self,
        organization_id: str,
        data: StockReceiptCreate,
        actor_user_id: str | None = None,
    ) -> StockMovement:
        try:
            await self._validate_active_references(
                organization_id, data.product_id, data.warehouse_id
            )
            balance = await self._locked_or_new_balance(
                organization_id, data.warehouse_id, data.product_id
            )
            total_value = StockValuationRules.money(data.quantity * data.unit_cost)
            self._increase_balance(balance, data.quantity, total_value)
            movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.ADJUSTMENT_IN,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=data.unit_cost,
                total_value=total_value,
                transfer_id=None,
                reference=data.reference,
                note=data.note,
            )
            if actor_user_id is not None:
                await InventoryAccountingService(self.session).post_movement(
                    organization_id, actor_user_id, movement
                )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        await self.session.refresh(movement)
        return movement

    async def _record_outbound_adjustment(
        self,
        organization_id: str,
        data: StockIssueCreate,
        actor_user_id: str | None = None,
    ) -> StockMovement:
        try:
            await self._validate_active_references(
                organization_id, data.product_id, data.warehouse_id
            )
            balance = await self.balances.get_for_update(
                organization_id, data.warehouse_id, data.product_id
            )
            unit_cost, total_value = self._decrease_balance(balance, data.quantity)
            movement = await self.movements.create(
                organization_id=organization_id,
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                movement_type=StockMovementType.ADJUSTMENT_OUT,
                movement_date=data.movement_date,
                quantity=data.quantity,
                unit_cost=unit_cost,
                total_value=total_value,
                transfer_id=None,
                reference=data.reference,
                note=data.note,
            )
            if actor_user_id is not None:
                await InventoryAccountingService(self.session).post_movement(
                    organization_id, actor_user_id, movement
                )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        await self.session.refresh(movement)
        return movement

    async def _validate_active_references(
        self, organization_id: str, product_id: str, warehouse_id: str
    ) -> tuple[Product, Warehouse]:
        product = await self.products.get_by_id(organization_id, product_id)
        if product is None or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active product not found",
            )
        warehouse = await self.warehouses.get_by_id(organization_id, warehouse_id)
        if warehouse is None or not warehouse.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active warehouse not found",
            )
        return product, warehouse

    async def _locked_or_new_balance(
        self, organization_id: str, warehouse_id: str, product_id: str
    ) -> StockBalance:
        balance = await self.balances.get_for_update(
            organization_id, warehouse_id, product_id
        )
        if balance is None:
            balance = await self.balances.create(
                organization_id, warehouse_id, product_id
            )
        return balance

    def _increase_balance(
        self, balance: StockBalance, quantity: Decimal, total_value: Decimal
    ) -> None:
        valued_balance = StockValuationRules.increase(
            self._valued_balance(balance), quantity, total_value
        )
        self._apply_valued_balance(balance, valued_balance)

    def _decrease_balance(
        self, balance: StockBalance | None, quantity: Decimal
    ) -> tuple[Decimal, Decimal]:
        if balance is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Insufficient stock quantity",
            )
        try:
            valued_balance, unit_cost, total_value = StockValuationRules.issue(
                self._valued_balance(balance), quantity
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        self._apply_valued_balance(balance, valued_balance)
        return unit_cost, total_value

    @staticmethod
    def _valued_balance(balance: StockBalance) -> ValuedStockBalance:
        return ValuedStockBalance(
            quantity=Decimal(balance.quantity),
            total_value=Decimal(balance.total_value),
            average_unit_cost=Decimal(balance.average_unit_cost),
        )

    @staticmethod
    def _apply_valued_balance(
        balance: StockBalance, valued_balance: ValuedStockBalance
    ) -> None:
        balance.quantity = valued_balance.quantity
        balance.total_value = valued_balance.total_value
        balance.average_unit_cost = valued_balance.average_unit_cost
