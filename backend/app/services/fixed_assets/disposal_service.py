import json
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.fixed_assets.depreciation.rules import DepreciationRules
from app.domain.fixed_assets.lifecycle.rules import FixedAssetLifecycleRules
from app.models.fixed_assets.disposal import FixedAssetDisposal
from app.repositories.fixed_assets.asset_repository import FixedAssetRepository
from app.repositories.fixed_assets.audit_repository import FixedAssetAuditRepository
from app.repositories.fixed_assets.configuration_repository import (
    FixedAssetAccountingProfileRepository,
    FixedAssetCategoryRepository,
)
from app.repositories.fixed_assets.depreciation_repository import (
    DepreciationScheduleRepository,
    FixedAssetDisposalRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.fixed_assets.disposal import FixedAssetDisposalCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetDisposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = FixedAssetRepository(session)
        self.categories = FixedAssetCategoryRepository(session)
        self.profiles = FixedAssetAccountingProfileRepository(session)
        self.schedule = DepreciationScheduleRepository(session)
        self.disposals = FixedAssetDisposalRepository(session)
        self.audit = FixedAssetAuditRepository(session)
        self.journal_entries = JournalEntryService(session)

    async def dispose(
        self,
        organization_id: str,
        actor_user_id: str,
        asset_id: str,
        data: FixedAssetDisposalCreate,
    ):
        asset = await self.assets.get_by_id(organization_id, asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        existing = await self.disposals.get_for_asset(organization_id, asset.id)
        try:
            FixedAssetLifecycleRules.validate_disposal(
                asset.status, existing is not None
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        due_lines = await self.schedule.list_due(
            organization_id, asset.id, data.disposal_date
        )
        if due_lines:
            raise HTTPException(
                status_code=422,
                detail="All depreciation due through disposal date must be posted first",
            )
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
        posted_lines = []
        for plan in asset.plans:
            posted_lines.extend(
                await self.schedule.list_for_plan(organization_id, plan.id)
            )
        accumulated = sum(
            (
                Decimal(line.depreciation_amount)
                for line in posted_lines
                if line.status == "POSTED"
            ),
            Decimal("0.00"),
        )
        nbv, gain, loss = DepreciationRules.calculate_disposal(
            Decimal(asset.acquisition_cost), accumulated, data.proceeds
        )
        lines = [
            JournalEntryLineCreate(
                account_id=profile.asset_account_id,
                credit=Decimal(asset.acquisition_cost),
                description=asset.name,
            )
        ]
        if accumulated > 0:
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.accumulated_depreciation_account_id,
                    debit=accumulated,
                    description=asset.name,
                )
            )
        if data.proceeds > 0:
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.disposal_proceeds_account_id,
                    debit=data.proceeds,
                    description=asset.name,
                )
            )
        if gain > 0:
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.disposal_gain_account_id,
                    credit=gain,
                    description=asset.name,
                )
            )
        if loss > 0:
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.disposal_loss_account_id,
                    debit=loss,
                    description=asset.name,
                )
            )
        entry = await self.journal_entries.create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=data.fiscal_period_id,
                entry_number=f"FA-DSP-{asset.id[:20]}",
                entry_date=data.disposal_date,
                description=f"Fixed asset disposal {asset.asset_code}",
                reference=asset.asset_code,
                lines=lines,
            ),
        )
        posted = await self.journal_entries.post_entry(organization_id, entry.id)
        disposal = await self.disposals.create(
            FixedAssetDisposal(
                organization_id=organization_id,
                asset_id=asset.id,
                disposal_date=data.disposal_date,
                disposal_type=data.disposal_type,
                proceeds=data.proceeds,
                asset_cost=asset.acquisition_cost,
                accumulated_depreciation=accumulated,
                net_book_value=nbv,
                gain_amount=gain,
                loss_amount=loss,
                status="POSTED",
                journal_entry_id=posted.id,
                posted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                posted_by_user_id=actor_user_id,
                notes=data.notes,
            )
        )
        asset.status = "DISPOSED"
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_DISPOSED",
            "FixedAssetDisposal",
            disposal.id,
            asset.id,
            previous_value=json.dumps({"status": "IN_SERVICE"}),
            new_value=json.dumps({"status": "DISPOSED", "journal_entry_id": posted.id}),
            reason=data.notes,
        )
        await self.session.commit()
        await self.session.refresh(disposal)
        return disposal
