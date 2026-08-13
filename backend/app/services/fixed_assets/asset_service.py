import json
from decimal import Decimal

from app.domain.fixed_assets.depreciation.rules import DepreciationRules
from app.domain.fixed_assets.lifecycle.rules import FixedAssetLifecycleRules
from app.models.fixed_assets.depreciation import (
    DepreciationPlan,
    DepreciationScheduleLine,
)
from app.repositories.fixed_assets.asset_repository import (
    FixedAssetComponentRepository,
    FixedAssetRepository,
)
from app.repositories.fixed_assets.audit_repository import FixedAssetAuditRepository
from app.repositories.fixed_assets.configuration_repository import (
    FixedAssetAccountingProfileRepository,
    FixedAssetCategoryRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.fixed_assets.asset import (
    FixedAssetAcquireRequest,
    FixedAssetCommissionRequest,
    FixedAssetComponentCreate,
    FixedAssetCreate,
    FixedAssetUpdate,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = FixedAssetRepository(session)
        self.components = FixedAssetComponentRepository(session)
        self.categories = FixedAssetCategoryRepository(session)
        self.profiles = FixedAssetAccountingProfileRepository(session)
        self.audit = FixedAssetAuditRepository(session)
        self.journal_entries = JournalEntryService(session)

    async def get_asset(self, organization_id: str, asset_id: str):
        asset = await self.assets.get_by_id(organization_id, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        return asset

    async def list_assets(
        self, organization_id: str, status_value: str | None, offset: int, limit: int
    ):
        return await self.assets.list(
            organization_id, status_value, max(offset, 0), min(max(limit, 1), 100)
        )

    async def create_asset(
        self, organization_id: str, actor_user_id: str, data: FixedAssetCreate
    ):
        if await self.assets.get_by_code(organization_id, data.asset_code):
            raise HTTPException(
                status_code=409, detail="Fixed asset code already exists"
            )
        category = await self.categories.get_by_id(organization_id, data.category_id)
        if category is None or not category.is_active:
            raise HTTPException(
                status_code=422, detail="An active fixed asset category is required"
            )
        try:
            asset = await self.assets.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "FIXED_ASSET_CREATED",
                "FixedAsset",
                asset.id,
                asset.id,
                new_value=json.dumps({"asset_code": asset.asset_code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Fixed asset code already exists"
            ) from exc
        return await self.get_asset(organization_id, asset.id)

    async def update_asset(
        self,
        organization_id: str,
        actor_user_id: str,
        asset_id: str,
        data: FixedAssetUpdate,
    ):
        asset = await self.assets.get_by_id(organization_id, asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        try:
            FixedAssetLifecycleRules.validate_asset_mutation(asset.status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        before = {field: getattr(asset, field) for field in data.model_fields_set}
        await self.assets.update(asset, data)
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_UPDATED",
            "FixedAsset",
            asset.id,
            asset.id,
            json.dumps(before, default=str),
            json.dumps(data.model_dump(exclude_unset=True), default=str),
        )
        await self.session.commit()
        return await self.get_asset(organization_id, asset.id)

    async def create_component(
        self,
        organization_id: str,
        actor_user_id: str,
        asset_id: str,
        data: FixedAssetComponentCreate,
    ):
        asset = await self.assets.get_by_id(organization_id, asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        try:
            FixedAssetLifecycleRules.validate_component_mutation(asset.status, "DRAFT")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        total = Decimal(
            await self.components.total_cost_for_asset(organization_id, asset.id)
        )
        if total + data.acquisition_cost > Decimal(asset.acquisition_cost):
            raise HTTPException(
                status_code=422,
                detail="Component costs cannot exceed asset acquisition cost",
            )
        component = await self.components.create(organization_id, asset.id, data)
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_COMPONENT_CREATED",
            "FixedAssetComponent",
            component.id,
            asset.id,
            new_value=json.dumps({"component_code": component.component_code}),
        )
        await self.session.commit()
        await self.session.refresh(component)
        return component

    async def acquire_asset(
        self,
        organization_id: str,
        actor_user_id: str,
        asset_id: str,
        data: FixedAssetAcquireRequest,
    ):
        asset = await self.assets.get_by_id(organization_id, asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        try:
            FixedAssetLifecycleRules.validate_asset_transition(asset.status, "ACQUIRED")
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
        if category is None or profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422, detail="Active accounting profile is required"
            )
        entry = await self.journal_entries.create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=data.fiscal_period_id,
                entry_number=f"FA-ACQ-{asset.id[:20]}",
                entry_date=asset.acquisition_date,
                description=f"Fixed asset acquisition {asset.asset_code}",
                reference=asset.asset_code,
                lines=[
                    JournalEntryLineCreate(
                        account_id=profile.asset_account_id,
                        debit=Decimal(asset.acquisition_cost),
                        description=asset.name,
                    ),
                    JournalEntryLineCreate(
                        account_id=profile.acquisition_counterpart_account_id,
                        credit=Decimal(asset.acquisition_cost),
                        description=asset.name,
                    ),
                ],
            ),
        )
        posted_entry = await self.journal_entries.post_entry(organization_id, entry.id)
        asset.status = "ACQUIRED"
        asset.acquisition_journal_entry_id = posted_entry.id
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_ACQUIRED",
            "FixedAsset",
            asset.id,
            asset.id,
            previous_value=json.dumps({"status": "DRAFT"}),
            new_value=json.dumps(
                {"status": "ACQUIRED", "journal_entry_id": posted_entry.id}
            ),
            reason=data.reason,
        )
        await self.session.commit()
        return await self.get_asset(organization_id, asset.id)

    async def commission_asset(
        self,
        organization_id: str,
        actor_user_id: str,
        asset_id: str,
        data: FixedAssetCommissionRequest,
    ):
        asset = await self.assets.get_by_id(organization_id, asset_id, True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Fixed asset not found")
        try:
            FixedAssetLifecycleRules.validate_asset_transition(
                asset.status, "IN_SERVICE"
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if data.available_for_use_date < asset.acquisition_date:
            raise HTTPException(
                status_code=422,
                detail="Available-for-use date cannot precede acquisition date",
            )
        category = await self.categories.get_by_id(organization_id, asset.category_id)
        if category is None:
            raise HTTPException(
                status_code=422, detail="Fixed asset category not found"
            )
        components = await self.components.list_for_asset(organization_id, asset.id)
        if not components:
            residual = DepreciationRules.money(
                Decimal(asset.acquisition_cost)
                * Decimal(category.default_residual_rate)
                / Decimal(100)
            )
            components = [
                await self.components.create(
                    organization_id,
                    asset.id,
                    FixedAssetComponentCreate(
                        component_code="PRIMARY",
                        name=asset.name,
                        acquisition_cost=Decimal(asset.acquisition_cost),
                        residual_value=residual,
                        useful_life_months=category.default_useful_life_months,
                        method=category.default_method,
                        declining_rate=category.default_declining_rate,
                    ),
                )
            ]
        for component in components:
            schedule = DepreciationRules.build_schedule(
                Decimal(component.acquisition_cost),
                Decimal(component.residual_value),
                data.available_for_use_date,
                component.useful_life_months,
                component.method,
                Decimal(component.declining_rate)
                if component.declining_rate is not None
                else None,
            )
            plan = DepreciationPlan(
                organization_id=organization_id,
                asset_id=asset.id,
                component_id=component.id,
                version_number=1,
                start_date=data.available_for_use_date,
                end_date=schedule[-1].scheduled_date
                if schedule
                else data.available_for_use_date,
                method=component.method,
                useful_life_months=component.useful_life_months,
                declining_rate=component.declining_rate,
                acquisition_cost=component.acquisition_cost,
                residual_value=component.residual_value,
                depreciable_base=DepreciationRules.money(
                    Decimal(component.acquisition_cost)
                    - Decimal(component.residual_value)
                ),
                convention="MONTHLY_PRORATA_DIE",
                parameters_snapshot=json.dumps(
                    {
                        "method": component.method,
                        "useful_life_months": component.useful_life_months,
                        "declining_rate": str(component.declining_rate),
                    }
                ),
                status="ACTIVE",
            )
            self.session.add(plan)
            await self.session.flush()
            for row in schedule:
                self.session.add(
                    DepreciationScheduleLine(
                        organization_id=organization_id,
                        plan_id=plan.id,
                        sequence_number=row.sequence_number,
                        scheduled_date=row.scheduled_date,
                        opening_net_book_value=row.opening_net_book_value,
                        depreciation_amount=row.depreciation_amount,
                        accumulated_depreciation=row.accumulated_depreciation,
                        closing_net_book_value=row.closing_net_book_value,
                    )
                )
            component.status = "ACTIVE"
        asset.status = "IN_SERVICE"
        asset.available_for_use_date = data.available_for_use_date
        await self.audit.append(
            organization_id,
            actor_user_id,
            "FIXED_ASSET_COMMISSIONED",
            "FixedAsset",
            asset.id,
            asset.id,
            previous_value=json.dumps({"status": "ACQUIRED"}),
            new_value=json.dumps(
                {
                    "status": "IN_SERVICE",
                    "available_for_use_date": str(data.available_for_use_date),
                }
            ),
            reason=data.reason,
        )
        await self.session.commit()
        return await self.get_asset(organization_id, asset.id)
