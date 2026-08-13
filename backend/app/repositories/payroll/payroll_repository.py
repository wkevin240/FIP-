from app.models.payroll.payroll import (
    PayrollCorrection,
    PayrollInput,
    PayrollSlip,
    PayrollSlipLine,
)
from app.models.payroll.payroll_period import PayrollPeriod
from app.schemas.payroll.configuration import PayrollPeriodCreate
from app.schemas.payroll.payroll import (
    PayrollCorrectionCreate,
    PayrollInputCreate,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class PayrollPeriodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail(self, statement):
        return statement.options(
            selectinload(PayrollPeriod.inputs),
            selectinload(PayrollPeriod.slips).selectinload(PayrollSlip.lines),
        )

    async def get_by_id(
        self, organization_id: str, payroll_period_id: str, for_update: bool = False
    ) -> PayrollPeriod | None:
        statement = select(PayrollPeriod).where(
            PayrollPeriod.organization_id == organization_id,
            PayrollPeriod.id == payroll_period_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(self._detail(statement))

    async def get_by_code(
        self, organization_id: str, period_code: str
    ) -> PayrollPeriod | None:
        return await self.session.scalar(
            self._detail(
                select(PayrollPeriod).where(
                    PayrollPeriod.organization_id == organization_id,
                    PayrollPeriod.period_code == period_code,
                )
            )
        )

    async def list(
        self, organization_id: str, status_value: str | None, offset: int, limit: int
    ) -> list[PayrollPeriod]:
        statement = select(PayrollPeriod).where(
            PayrollPeriod.organization_id == organization_id
        )
        if status_value is not None:
            statement = statement.where(PayrollPeriod.status == status_value)
        result = await self.session.scalars(
            self._detail(
                statement.order_by(PayrollPeriod.start_date.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return list(result)

    async def create(
        self, organization_id: str, data: PayrollPeriodCreate
    ) -> PayrollPeriod:
        payroll_period = PayrollPeriod(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(payroll_period)
        await self.session.flush()
        return payroll_period


class PayrollInputRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_period(
        self, organization_id: str, payroll_period_id: str
    ) -> list[PayrollInput]:
        result = await self.session.scalars(
            select(PayrollInput)
            .where(
                PayrollInput.organization_id == organization_id,
                PayrollInput.payroll_period_id == payroll_period_id,
            )
            .order_by(PayrollInput.employee_id, PayrollInput.created_at)
        )
        return list(result)

    async def create(
        self,
        organization_id: str,
        payroll_period_id: str,
        created_by_user_id: str,
        data: PayrollInputCreate,
    ) -> PayrollInput:
        payroll_input = PayrollInput(
            organization_id=organization_id,
            payroll_period_id=payroll_period_id,
            created_by_user_id=created_by_user_id,
            **data.model_dump(),
        )
        self.session.add(payroll_input)
        await self.session.flush()
        return payroll_input


class PayrollSlipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, payroll_slip_id: str, for_update: bool = False
    ) -> PayrollSlip | None:
        statement = (
            select(PayrollSlip)
            .options(selectinload(PayrollSlip.lines))
            .where(
                PayrollSlip.organization_id == organization_id,
                PayrollSlip.id == payroll_slip_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_for_period(
        self, organization_id: str, payroll_period_id: str
    ) -> list[PayrollSlip]:
        result = await self.session.scalars(
            select(PayrollSlip)
            .options(selectinload(PayrollSlip.lines))
            .where(
                PayrollSlip.organization_id == organization_id,
                PayrollSlip.payroll_period_id == payroll_period_id,
            )
            .order_by(PayrollSlip.slip_number)
        )
        return list(result)

    async def replace_calculated_for_period(
        self,
        payroll_period: PayrollPeriod,
        slips: list[PayrollSlip],
    ) -> None:
        for existing_slip in list(payroll_period.slips):
            await self.session.delete(existing_slip)
        for slip in slips:
            payroll_period.slips.append(slip)
        await self.session.flush()

    async def build_slip(
        self, payload: dict[str, object], lines: list[dict[str, object]]
    ) -> PayrollSlip:
        slip = PayrollSlip(**payload)
        for line in lines:
            slip.lines.append(PayrollSlipLine(**line))
        return slip

    async def create_correction(
        self,
        organization_id: str,
        source_slip_id: str,
        requested_by_user_id: str,
        data: PayrollCorrectionCreate,
    ) -> PayrollCorrection:
        correction = PayrollCorrection(
            organization_id=organization_id,
            source_slip_id=source_slip_id,
            requested_by_user_id=requested_by_user_id,
            **data.model_dump(),
        )
        self.session.add(correction)
        await self.session.flush()
        return correction
