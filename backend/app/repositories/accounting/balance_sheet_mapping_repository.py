from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.models.accounting.balance_sheet_mapping import (
    BALANCE_SHEET_CATEGORIES,
    BalanceSheetAccountMapping,
)


class BalanceSheetMappingConflictError(ValueError):
    """Raised when a balance-sheet mapping overlaps an existing effective rule."""


class BalanceSheetMappingRepository:
    """Tenant-scoped persistence boundary for explicit balance-sheet mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _validate(
        category: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        if category not in BALANCE_SHEET_CATEGORIES:
            raise ValueError(f"unsupported balance-sheet category: {category}")
        if not rule_version.strip():
            raise ValueError("rule_version must not be blank")
        if effective_to is not None and effective_to < effective_from:
            raise ValueError("effective_to must be on or after effective_from")

    async def _ensure_account(self, organization_id: str, account_id: str) -> None:
        exists = await self.session.scalar(
            select(Account.id).where(
                Account.id == account_id,
                Account.organization_id == organization_id,
            )
        )
        if exists is None:
            raise LookupError("account not found for organization")

    async def _ensure_no_overlap(
        self,
        *,
        organization_id: str,
        account_id: str,
        rule_version: str,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        filters = [
            BalanceSheetAccountMapping.organization_id == organization_id,
            BalanceSheetAccountMapping.account_id == account_id,
            BalanceSheetAccountMapping.rule_version == rule_version,
            BalanceSheetAccountMapping.effective_from <= (
                effective_to if effective_to is not None else date.max
            ),
            (
                BalanceSheetAccountMapping.effective_to.is_(None)
                | (BalanceSheetAccountMapping.effective_to >= effective_from)
            ),
        ]
        if await self.session.scalar(
            select(BalanceSheetAccountMapping.id).where(*filters).limit(1)
        ) is not None:
            raise BalanceSheetMappingConflictError(
                "balance-sheet mapping effective range overlaps an existing mapping"
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
    ) -> BalanceSheetAccountMapping:
        self._validate(category, rule_version, effective_from, effective_to)
        await self._ensure_account(organization_id, account_id)
        await self._ensure_no_overlap(
            organization_id=organization_id,
            account_id=account_id,
            rule_version=rule_version,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        mapping = BalanceSheetAccountMapping(
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

    async def list_for_period(
        self,
        organization_id: str,
        rule_version: str,
        period_start: date,
        period_end: date,
    ) -> list[BalanceSheetAccountMapping]:
        if period_start > period_end:
            raise ValueError("period_start must be on or before period_end")
        if not rule_version.strip():
            raise ValueError("rule_version must not be blank")
        result = await self.session.scalars(
            select(BalanceSheetAccountMapping)
            .where(
                BalanceSheetAccountMapping.organization_id == organization_id,
                BalanceSheetAccountMapping.rule_version == rule_version,
                BalanceSheetAccountMapping.effective_from <= period_end,
                (
                    BalanceSheetAccountMapping.effective_to.is_(None)
                    | (BalanceSheetAccountMapping.effective_to >= period_start)
                ),
            )
            .order_by(
                BalanceSheetAccountMapping.account_id,
                BalanceSheetAccountMapping.effective_from,
                BalanceSheetAccountMapping.id,
            )
        )
        return list(result)

    async def list_effective_at(
        self,
        organization_id: str,
        rule_version: str,
        as_of_date: date,
    ) -> list[BalanceSheetAccountMapping]:
        """Return mappings effective on the balance-sheet snapshot date.

        A balance sheet is a point-in-time closing statement. Historical mappings
        that ended before ``as_of_date`` must not participate in the closing
        classification merely because they overlap the reporting period.
        """
        if not rule_version.strip():
            raise ValueError("rule_version must not be blank")
        result = await self.session.scalars(
            select(BalanceSheetAccountMapping)
            .where(
                BalanceSheetAccountMapping.organization_id == organization_id,
                BalanceSheetAccountMapping.rule_version == rule_version,
                BalanceSheetAccountMapping.effective_from <= as_of_date,
                (
                    BalanceSheetAccountMapping.effective_to.is_(None)
                    | (BalanceSheetAccountMapping.effective_to >= as_of_date)
                ),
            )
            .order_by(
                BalanceSheetAccountMapping.account_id,
                BalanceSheetAccountMapping.effective_from,
                BalanceSheetAccountMapping.id,
            )
        )
        return list(result)
