from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.inventory.stock_movement import StockMovement
from app.repositories.accounting.journal_repository import JournalRepository
from app.repositories.inventory.inventory_accounting_repository import (
    InventoryAccountingRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.inventory.accounting import InventoryAccountingProfileCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class InventoryAccountingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InventoryAccountingRepository(session)
        self.journals = JournalRepository(session)
        self.entries = JournalEntryService(session)
        self.audit = AuditService(session)

    async def configure_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: InventoryAccountingProfileCreate,
    ):
        if await self.repository.get_profile(organization_id, for_update=True):
            raise HTTPException(
                status_code=409, detail="Inventory accounting profile already exists"
            )
        await self._validate_profile(organization_id, data.model_dump())
        profile = await self.repository.create_profile(
            organization_id, data.model_dump()
        )
        await self.audit.record(
            organization_id,
            actor_user_id,
            "INVENTORY_ACCOUNTING_PROFILE_CONFIGURED",
            "InventoryAccountingProfile",
            profile.id,
            new_value=data.model_dump(),
        )
        await self.session.commit()
        return profile

    async def get_profile(self, organization_id: str):
        profile = await self.repository.get_profile(organization_id)
        if profile is None:
            raise HTTPException(
                status_code=404, detail="Inventory accounting profile not found"
            )
        return profile

    async def post_movement(
        self, organization_id: str, actor_user_id: str, movement: StockMovement
    ):
        existing = await self.repository.get_posting(organization_id, movement.id)
        if existing:
            return existing
        value = Decimal(movement.total_value)
        if value <= Decimal("0.00"):
            raise HTTPException(
                status_code=422, detail="Zero-value stock movements cannot be posted"
            )
        profile = await self.repository.get_profile(organization_id, for_update=True)
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422,
                detail="Inventory accounting is not ready: active profile is required",
            )
        values = {
            name: getattr(profile, name)
            for name in (
                "journal_id",
                "inventory_account_id",
                "receipt_counterpart_account_id",
                "cost_of_sales_account_id",
                "adjustment_gain_account_id",
                "adjustment_loss_account_id",
            )
        }
        await self._validate_profile(organization_id, values)
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= movement.movement_date,
                FiscalPeriod.end_date >= movement.movement_date,
            )
            .with_for_update()
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=422, detail="Fiscal period is not open")
        debit_id, credit_id = self._accounts_for_movement(
            movement.movement_type, profile
        )
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"STK-{movement.id[:20]}",
                entry_date=movement.movement_date,
                description=f"Inventory {movement.movement_type} {movement.id}",
                reference=movement.reference,
                lines=[
                    JournalEntryLineCreate(account_id=debit_id, debit=value),
                    JournalEntryLineCreate(account_id=credit_id, credit=value),
                ],
            ),
            actor_user_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_user_id, commit=False
        )
        posting = await self.repository.create_posting(
            organization_id, movement.movement_type, movement.id, posted.id
        )
        await self.audit.record(
            organization_id,
            actor_user_id,
            "INVENTORY_MOVEMENT_POSTED_TO_ACCOUNTING",
            "StockMovement",
            movement.id,
            new_value={
                "journal_entry_id": posted.id,
                "movement_type": movement.movement_type,
                "total_value": str(value),
            },
            transaction_id=posted.id,
        )
        return posting

    async def _validate_profile(self, organization_id: str, values: dict[str, object]):
        journal = await self.journals.get_by_id(
            organization_id, str(values["journal_id"])
        )
        if journal is None or not journal.is_active:
            raise HTTPException(status_code=422, detail="Active journal not found")
        expected = {
            "inventory_account_id": "ASSET",
            "receipt_counterpart_account_id": "LIABILITY",
            "cost_of_sales_account_id": "EXPENSE",
            "adjustment_gain_account_id": "REVENUE",
            "adjustment_loss_account_id": "EXPENSE",
        }
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.id.in_([str(values[key]) for key in expected]),
                    Account.is_active.is_(True),
                )
            )
        )
        by_id = {account.id: account for account in accounts}
        if any(
            by_id.get(str(values[key])) is None
            or by_id[str(values[key])].account_type != account_type
            for key, account_type in expected.items()
        ):
            raise HTTPException(
                status_code=422,
                detail="Inventory accounting profile requires active tenant-scoped accounts of the expected types",
            )

    @staticmethod
    def _accounts_for_movement(movement_type: str, profile):
        if movement_type == "RECEIPT":
            return profile.inventory_account_id, profile.receipt_counterpart_account_id
        if movement_type == "ISSUE":
            return profile.cost_of_sales_account_id, profile.inventory_account_id
        if movement_type == "ADJUSTMENT_IN":
            return profile.inventory_account_id, profile.adjustment_gain_account_id
        if movement_type == "ADJUSTMENT_OUT":
            return profile.adjustment_loss_account_id, profile.inventory_account_id
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Internal transfers do not create organization-level accounting entries",
        )
