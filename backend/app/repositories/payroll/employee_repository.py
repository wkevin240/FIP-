from datetime import date

from app.models.payroll.employee import Employee, EmploymentContract
from app.schemas.payroll.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmploymentContractCreate,
    EmploymentContractUpdate,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, employee_id: str
    ) -> Employee | None:
        return await self.session.scalar(
            select(Employee).where(
                Employee.organization_id == organization_id, Employee.id == employee_id
            )
        )

    async def get_by_code(
        self, organization_id: str, employee_code: str
    ) -> Employee | None:
        return await self.session.scalar(
            select(Employee).where(
                Employee.organization_id == organization_id,
                Employee.employee_code == employee_code,
            )
        )

    async def list(
        self, organization_id: str, active_only: bool, offset: int, limit: int
    ) -> list[Employee]:
        statement = select(Employee).where(Employee.organization_id == organization_id)
        if active_only:
            statement = statement.where(Employee.is_active.is_(True))
        result = await self.session.scalars(
            statement.order_by(Employee.employee_code).offset(offset).limit(limit)
        )
        return list(result)

    async def create(self, organization_id: str, data: EmployeeCreate) -> Employee:
        employee = Employee(organization_id=organization_id, **data.model_dump())
        self.session.add(employee)
        await self.session.flush()
        return employee

    async def update(self, employee: Employee, data: EmployeeUpdate) -> None:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(employee, field, value)


class EmploymentContractRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, contract_id: str, for_update: bool = False
    ) -> EmploymentContract | None:
        statement = select(EmploymentContract).where(
            EmploymentContract.organization_id == organization_id,
            EmploymentContract.id == contract_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_for_employee(
        self, organization_id: str, employee_id: str
    ) -> list[EmploymentContract]:
        result = await self.session.scalars(
            select(EmploymentContract)
            .where(
                EmploymentContract.organization_id == organization_id,
                EmploymentContract.employee_id == employee_id,
            )
            .order_by(EmploymentContract.start_date.desc())
        )
        return list(result)

    async def active_for_date(
        self, organization_id: str, employee_id: str, as_of: date
    ) -> EmploymentContract | None:
        return await self.session.scalar(
            select(EmploymentContract)
            .where(
                EmploymentContract.organization_id == organization_id,
                EmploymentContract.employee_id == employee_id,
                EmploymentContract.status == "ACTIVE",
                EmploymentContract.start_date <= as_of,
                or_(
                    EmploymentContract.end_date.is_(None),
                    EmploymentContract.end_date >= as_of,
                ),
            )
            .order_by(EmploymentContract.start_date.desc())
        )

    async def has_overlap(
        self,
        organization_id: str,
        employee_id: str,
        start_date: date,
        end_date: date | None,
        exclude_contract_id: str | None = None,
    ) -> bool:
        statement = select(EmploymentContract.id).where(
            EmploymentContract.organization_id == organization_id,
            EmploymentContract.employee_id == employee_id,
            EmploymentContract.status.in_(["DRAFT", "ACTIVE", "SUSPENDED"]),
            or_(
                EmploymentContract.end_date.is_(None),
                EmploymentContract.end_date >= start_date,
            ),
        )
        if end_date is not None:
            statement = statement.where(EmploymentContract.start_date <= end_date)
        if exclude_contract_id is not None:
            statement = statement.where(EmploymentContract.id != exclude_contract_id)
        return await self.session.scalar(statement) is not None

    async def create(
        self, organization_id: str, employee_id: str, data: EmploymentContractCreate
    ) -> EmploymentContract:
        contract = EmploymentContract(
            organization_id=organization_id,
            employee_id=employee_id,
            **data.model_dump(),
        )
        self.session.add(contract)
        await self.session.flush()
        return contract

    async def update(
        self, contract: EmploymentContract, data: EmploymentContractUpdate
    ) -> None:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(contract, field, value)
