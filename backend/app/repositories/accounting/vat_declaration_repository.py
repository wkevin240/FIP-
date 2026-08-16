from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.vat import VATEntry
from app.models.accounting.vat_declaration import VATDeclaration


class VATDeclarationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_period(
        self, organization_id: str, fiscal_period_id: str
    ) -> FiscalPeriod | None:
        return await self.session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.id == fiscal_period_id,
            )
        )

    async def get_declaration(
        self, organization_id: str, declaration_id: str
    ) -> VATDeclaration | None:
        return await self.session.scalar(
            select(VATDeclaration).where(
                VATDeclaration.organization_id == organization_id,
                VATDeclaration.id == declaration_id,
            )
        )

    async def get_by_period(
        self, organization_id: str, fiscal_period_id: str
    ) -> VATDeclaration | None:
        return await self.session.scalar(
            select(VATDeclaration).where(
                VATDeclaration.organization_id == organization_id,
                VATDeclaration.fiscal_period_id == fiscal_period_id,
            )
        )

    async def list_declarations(self, organization_id: str) -> list[VATDeclaration]:
        return list(
            await self.session.scalars(
                select(VATDeclaration)
                .where(VATDeclaration.organization_id == organization_id)
                .order_by(VATDeclaration.created_at.desc())
            )
        )

    async def totals(
        self, organization_id: str, start_date: date, end_date: date
    ) -> dict[str, object]:
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (VATEntry.direction == "OUTPUT", VATEntry.vat_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("output"),
                func.coalesce(
                    func.sum(
                        case(
                            (VATEntry.direction == "INPUT", VATEntry.vat_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("input"),
            ).where(
                VATEntry.organization_id == organization_id,
                VATEntry.tax_date >= start_date,
                VATEntry.tax_date <= end_date,
            )
        )
        row = result.one()
        return {"OUTPUT": row.output, "INPUT": row.input}

    async def create(self, declaration: VATDeclaration) -> VATDeclaration:
        self.session.add(declaration)
        await self.session.flush()
        return declaration
