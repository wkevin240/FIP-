from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.financial_statement_mapping import FinancialStatementMapping
from app.schemas.accounting.professional_reporting import (
    FinancialStatementMappingCreate,
)


class FinancialStatementMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, mapping_id: str
    ) -> FinancialStatementMapping | None:
        return await self.session.scalar(
            select(FinancialStatementMapping).where(
                FinancialStatementMapping.organization_id == organization_id,
                FinancialStatementMapping.id == mapping_id,
            )
        )

    async def get_for_account_and_statement(
        self,
        organization_id: str,
        account_id: str,
        framework: str,
        statement_code: str,
    ) -> FinancialStatementMapping | None:
        return await self.session.scalar(
            select(FinancialStatementMapping).where(
                FinancialStatementMapping.organization_id == organization_id,
                FinancialStatementMapping.account_id == account_id,
                FinancialStatementMapping.framework == framework,
                FinancialStatementMapping.statement_code == statement_code,
            )
        )

    async def list_active(
        self, organization_id: str, framework: str, statement_code: str
    ) -> list[FinancialStatementMapping]:
        result = await self.session.scalars(
            select(FinancialStatementMapping)
            .where(
                FinancialStatementMapping.organization_id == organization_id,
                FinancialStatementMapping.framework == framework,
                FinancialStatementMapping.statement_code == statement_code,
                FinancialStatementMapping.is_active.is_(True),
            )
            .order_by(
                FinancialStatementMapping.display_order,
                FinancialStatementMapping.section_code,
                FinancialStatementMapping.line_code,
            )
        )
        return list(result)

    async def create(
        self, organization_id: str, data: FinancialStatementMappingCreate
    ) -> FinancialStatementMapping:
        mapping = FinancialStatementMapping(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping
