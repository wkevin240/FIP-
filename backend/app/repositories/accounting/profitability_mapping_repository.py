from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.calculation.accounting_profitability import CATEGORY_CODES
from app.models.accounting.account import Account
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping


class ProfitabilityMappingConflictError(ValueError):
    """Raised when a mapping would overlap an existing scoped rule."""


class ProfitabilityMappingNotFoundError(LookupError):
    """Raised when a tenant-scoped mapping cannot be found."""


class ProfitabilityMappingRepository:
    """Tenant-scoped persistence boundary for explicit profitability mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _validate_mapping_values(
        category: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        if category not in CATEGORY_CODES:
            raise ValueError(f"unsupported profitability category: {category}")
        if not rule_version.strip():
            raise ValueError("rule_version must not be blank")
        if effective_to is not None and effective_to < effective_from:
            raise ValueError("effective_to must be on or after effective_from")

    async def _ensure_account_belongs_to_organization(
        self,
        organization_id: str,
        account_id: str,
    ) -> None:
        account_exists = await self.session.scalar(
            select(Account.id).where(
                Account.id == account_id,
                Account.organization_id == organization_id,
            )
        )
        if account_exists is None:
            raise LookupError("account not found for organization")

    async def _ensure_no_overlap(
        self,
        *,
        organization_id: str,
        account_id: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None,
        exclude_id: str | None = None,
    ) -> None:
        filters = [
            ProfitabilityAccountMapping.organization_id == organization_id,
            ProfitabilityAccountMapping.account_id == account_id,
            ProfitabilityAccountMapping.rule_version == rule_version,
            ProfitabilityAccountMapping.effective_from <= (
                effective_to if effective_to is not None else date.max
            ),
            (
                ProfitabilityAccountMapping.effective_to.is_(None)
                | (ProfitabilityAccountMapping.effective_to >= effective_from)
            ),
        ]
        if exclude_id is not None:
            filters.append(ProfitabilityAccountMapping.id != exclude_id)
        conflict = await self.session.scalar(select(ProfitabilityAccountMapping.id).where(*filters).limit(1))
        if conflict is not None:
            raise ProfitabilityMappingConflictError(
                "profitability mapping effective range overlaps an existing mapping"
            )

    async def create(
        self,
        *,
        organization_id: str,
        account_id: str,
        category: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None = None,
    ) -> ProfitabilityAccountMapping:
        self._validate_mapping_values(category, rule_version, effective_from, effective_to)
        await self._ensure_account_belongs_to_organization(organization_id, account_id)
        await self._ensure_no_overlap(
            organization_id=organization_id,
            account_id=account_id,
            rule_version=rule_version,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        mapping = ProfitabilityAccountMapping(
            organization_id=organization_id,
            account_id=account_id,
            category=category,
            rule_version=rule_version,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def update(
        self,
        mapping_id: str,
        *,
        organization_id: str,
        account_id: str,
        category: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None = None,
    ) -> ProfitabilityAccountMapping:
        self._validate_mapping_values(category, rule_version, effective_from, effective_to)
        mapping = await self.session.scalar(
            select(ProfitabilityAccountMapping).where(
                ProfitabilityAccountMapping.id == mapping_id,
                ProfitabilityAccountMapping.organization_id == organization_id,
            )
        )
        if mapping is None:
            raise ProfitabilityMappingNotFoundError("profitability mapping not found")

        await self._ensure_account_belongs_to_organization(organization_id, account_id)
        await self._ensure_no_overlap(
            organization_id=organization_id,
            account_id=account_id,
            rule_version=rule_version,
            effective_from=effective_from,
            effective_to=effective_to,
            exclude_id=mapping_id,
        )
        mapping.account_id = account_id
        mapping.category = category
        mapping.rule_version = rule_version
        mapping.effective_from = effective_from
        mapping.effective_to = effective_to
        await self.session.flush()
        return mapping

    async def list_for_period(
        self,
        organization_id: str,
        rule_version: str,
        period_start: date,
        period_end: date,
    ) -> list[ProfitabilityAccountMapping]:
        if period_start > period_end:
            raise ValueError("period_start must be on or before period_end")
        if not rule_version.strip():
            raise ValueError("rule_version must not be blank")
        result = await self.session.scalars(
            select(ProfitabilityAccountMapping)
            .where(
                ProfitabilityAccountMapping.organization_id == organization_id,
                ProfitabilityAccountMapping.rule_version == rule_version,
                ProfitabilityAccountMapping.effective_from <= period_end,
                (
                    ProfitabilityAccountMapping.effective_to.is_(None)
                    | (ProfitabilityAccountMapping.effective_to >= period_start)
                ),
            )
            .order_by(
                ProfitabilityAccountMapping.account_id,
                ProfitabilityAccountMapping.effective_from,
                ProfitabilityAccountMapping.id,
            )
        )
        return list(result)
