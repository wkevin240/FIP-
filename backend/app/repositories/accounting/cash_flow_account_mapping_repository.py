from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.cash_flow_account_mapping import CashFlowAccountMapping
from app.schemas.accounting.cash_flow import CashFlowAccountMappingCreate


class CashFlowAccountMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_account(
        self, organization_id: str, account_id: str
    ) -> CashFlowAccountMapping | None:
        return await self.session.scalar(
            select(CashFlowAccountMapping).where(
                CashFlowAccountMapping.organization_id == organization_id,
                CashFlowAccountMapping.account_id == account_id,
            )
        )

    async def list_active(self, organization_id: str) -> list[CashFlowAccountMapping]:
        result = await self.session.scalars(
            select(CashFlowAccountMapping)
            .where(
                CashFlowAccountMapping.organization_id == organization_id,
                CashFlowAccountMapping.is_active.is_(True),
            )
            .order_by(
                CashFlowAccountMapping.is_cash_account.desc(),
                CashFlowAccountMapping.account_id,
            )
        )
        return list(result)

    async def create(
        self, organization_id: str, data: CashFlowAccountMappingCreate
    ) -> CashFlowAccountMapping:
        mapping = CashFlowAccountMapping(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping
