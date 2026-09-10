from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping


class ProfitabilityMappingRepository:
    """Read/write persistence boundary for explicit profitability mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_period(
        self,
        organization_id: str,
        rule_version: str,
        period_start: date,
        period_end: date,
    ) -> list[ProfitabilityAccountMapping]:
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
