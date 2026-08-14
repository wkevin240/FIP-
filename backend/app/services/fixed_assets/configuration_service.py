import json

from app.models.accounting.account import Account
from app.models.accounting.journal import Journal
from app.models.fixed_assets.asset_category import (
    FixedAssetAccountingProfile,
    FixedAssetCategory,
)
from app.repositories.fixed_assets.audit_repository import FixedAssetAuditRepository
from app.repositories.fixed_assets.configuration_repository import (
    FixedAssetAccountingProfileRepository,
    FixedAssetCategoryRepository,
)
from app.schemas.fixed_assets.configuration import (
    FixedAssetAccountingProfileCreate,
    FixedAssetCategoryCreate,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetConfigurationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profiles = FixedAssetAccountingProfileRepository(session)
        self.categories = FixedAssetCategoryRepository(session)
        self.audit = FixedAssetAuditRepository(session)

    async def get_profile(
        self, organization_id: str, profile_id: str
    ) -> FixedAssetAccountingProfile:
        profile = await self.profiles.get_by_id(organization_id, profile_id)
        if profile is None:
            raise HTTPException(
                status_code=404, detail="Fixed asset accounting profile not found"
            )
        return profile

    async def create_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: FixedAssetAccountingProfileCreate,
    ) -> FixedAssetAccountingProfile:
        if await self.profiles.get_by_code(organization_id, data.profile_code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fixed asset accounting profile code already exists",
            )
        await self._validate_accounting_references(organization_id, data)
        try:
            profile = await self.profiles.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "FIXED_ASSET_ACCOUNTING_PROFILE_CREATED",
                "FixedAssetAccountingProfile",
                profile.id,
                new_value=json.dumps({"profile_code": profile.profile_code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fixed asset accounting profile code already exists",
            ) from exc
        await self.session.refresh(profile)
        return profile

    async def get_category(
        self, organization_id: str, category_id: str
    ) -> FixedAssetCategory:
        category = await self.categories.get_by_id(organization_id, category_id)
        if category is None:
            raise HTTPException(
                status_code=404, detail="Fixed asset category not found"
            )
        return category

    async def list_categories(
        self, organization_id: str, active_only: bool
    ) -> list[FixedAssetCategory]:
        return await self.categories.list(organization_id, active_only)

    async def create_category(
        self,
        organization_id: str,
        actor_user_id: str,
        data: FixedAssetCategoryCreate,
    ) -> FixedAssetCategory:
        if await self.categories.get_by_code(organization_id, data.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fixed asset category code already exists",
            )
        profile = await self.profiles.get_by_id(
            organization_id, data.accounting_profile_id
        )
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active fixed asset accounting profile is required",
            )
        try:
            category = await self.categories.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "FIXED_ASSET_CATEGORY_CREATED",
                "FixedAssetCategory",
                category.id,
                new_value=json.dumps({"code": category.code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fixed asset category code already exists",
            ) from exc
        await self.session.refresh(category)
        return category

    async def _validate_accounting_references(
        self, organization_id: str, data: FixedAssetAccountingProfileCreate
    ) -> None:
        journal = await self.session.scalar(
            select(Journal).where(
                Journal.organization_id == organization_id,
                Journal.id == data.journal_id,
                Journal.is_active.is_(True),
            )
        )
        if journal is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active fixed asset journal is required",
            )
        expected_types = {
            data.asset_account_id: "ASSET",
            data.accumulated_depreciation_account_id: "ASSET",
            data.depreciation_expense_account_id: "EXPENSE",
            data.disposal_gain_account_id: "REVENUE",
            data.disposal_loss_account_id: "EXPENSE",
        }
        account_ids = {
            *expected_types,
            data.acquisition_counterpart_account_id,
            data.disposal_proceeds_account_id,
        }
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.id.in_(account_ids),
                    Account.is_active.is_(True),
                )
            )
        )
        if len(accounts) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All fixed asset profile accounts must be active",
            )
        account_types = {account.id: account.account_type for account in accounts}
        for account_id, expected_type in expected_types.items():
            if account_types[account_id] != expected_type:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Fixed asset profile account must be {expected_type}",
                )
