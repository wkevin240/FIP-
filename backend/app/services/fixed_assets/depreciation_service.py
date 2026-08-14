import json
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.fixed_assets.lifecycle.rules import FixedAssetLifecycleRules
from app.repositories.fixed_assets.asset_repository import FixedAssetRepository
from app.repositories.fixed_assets.audit_repository import FixedAssetAuditRepository
from app.repositories.fixed_assets.configuration_repository import (
    FixedAssetAccountingProfileRepository,
    FixedAssetCategoryRepository,
)
from app.repositories.fixed_assets.depreciation_repository import (
    DepreciationPlanRepository,
    DepreciationScheduleRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


class DepreciationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = FixedAssetRepository(session)
        self.categories = FixedAssetCategoryRepository(session)
        self.profiles = FixedAssetAccountingProfileRepository(session)
        self.plans = DepreciationPlanRepository(session)
        self.schedule = DepreciationScheduleRepository(session)
        self.audit = FixedAssetAuditRepository(session)
        self.journal_entries = JournalEntryService(session)

    async def list_plans(self, organization_id: str, asset_id: str):
        asset = await self.assets.get_by_id(organization_id, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        return await self.plans.list_for_asset(organization_id, asset_id)

    async def list_schedule(self, organization_id: str, plan_id: str):
        return await self.schedule.list_for_plan(organization_id, plan_id)

    async def post_schedule_line(
        self,
        organization_id: str,
        actor_user_id: str,
        schedule_line_id: str,
        fiscal_period_id: str,
    ):
        line = await self.schedule.get_by_id(organization_id, schedule_line_id, True)
        if line is None:
            raise HTTPException(
                status_code=404, detail="Depreciation schedule line not found"
            )
        asset = await self.assets.get_by_id(organization_id, line.plan.asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        try:
            FixedAssetLifecycleRules.validate_schedule_posting(
                asset.status, line.plan.status, line.status
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        category = await self.categories.get_by_id(organization_id, asset.category_id)
        profile = (
            await self.profiles.get_by_id(
                organization_id, category.accounting_profile_id
            )
            if category
            else None
        )
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422,
                detail="Active fixed asset accounting profile is required",
            )
        entry = await self.journal_entries.create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=fiscal_period_id,
                entry_number=f"FA-DEP-{line.id[:20]}",
                entry_date=line.scheduled_date,
                description=f"Depreciation {asset.asset_code}",
                reference=asset.asset_code,
                lines=[
                    JournalEntryLineCreate(
                        account_id=profile.depreciation_expense_account_id,
                        debit=Decimal(line.depreciation_amount),
                        description=asset.name,
                    ),
                    JournalEntryLineCreate(
                        account_id=profile.accumulated_depreciation_account_id,
                        credit=Decimal(line.depreciation_amount),
                        description=asset.name,
                    ),
                ],
            ),
        )
        posted = await self.journal_entries.post_entry(organization_id, entry.id)
        line.status = "POSTED"
        line.fiscal_period_id = fiscal_period_id
        line.journal_entry_id = posted.id
        line.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        line.posted_by_user_id = actor_user_id
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_DEPRECIATION_POSTED",
            "DepreciationScheduleLine",
            line.id,
            asset.id,
            previous_value=json.dumps({"status": "PLANNED"}),
            new_value=json.dumps({"status": "POSTED", "journal_entry_id": posted.id}),
        )
        await self.session.commit()
        return await self.schedule.get_by_id(organization_id, line.id)
