import json

from app.domain.payroll.lifecycle.rules import PayrollLifecycleRules
from app.models.payroll.employee import Employee, EmploymentContract
from app.repositories.payroll.audit_repository import PayrollAuditRepository
from app.repositories.payroll.employee_repository import (
    EmployeeRepository,
    EmploymentContractRepository,
)
from app.schemas.payroll.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmploymentContractCreate,
    EmploymentContractUpdate,
)
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.contracts = EmploymentContractRepository(session)
        self.audit = PayrollAuditRepository(session)

    async def get_employee(self, organization_id: str, employee_id: str) -> Employee:
        employee = await self.employees.get_by_id(organization_id, employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Payroll employee not found")
        return employee

    async def list_employees(
        self, organization_id: str, active_only: bool, offset: int, limit: int
    ) -> list[Employee]:
        return await self.employees.list(
            organization_id, active_only, max(offset, 0), min(max(limit, 1), 100)
        )

    async def create_employee(
        self, organization_id: str, actor_user_id: str, data: EmployeeCreate
    ) -> Employee:
        if await self.employees.get_by_code(organization_id, data.employee_code):
            raise HTTPException(
                status_code=409, detail="Payroll employee code already exists"
            )
        try:
            employee = await self.employees.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "EMPLOYEE_CREATED",
                "PayrollEmployee",
                employee.id,
                new_value=json.dumps({"employee_code": employee.employee_code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll employee code already exists",
            ) from exc
        await self.session.refresh(employee)
        return employee

    async def update_employee(
        self,
        organization_id: str,
        actor_user_id: str,
        employee_id: str,
        data: EmployeeUpdate,
    ) -> Employee:
        employee = await self.get_employee(organization_id, employee_id)
        previous = {field: getattr(employee, field) for field in data.model_fields_set}
        await self.employees.update(employee, data)
        await self.audit.append(
            organization_id,
            actor_user_id,
            "EMPLOYEE_UPDATED",
            "PayrollEmployee",
            employee.id,
            previous_value=json.dumps(previous, default=str),
            new_value=json.dumps(data.model_dump(exclude_unset=True), default=str),
        )
        await self.session.commit()
        return await self.get_employee(organization_id, employee.id)

    async def create_contract(
        self,
        organization_id: str,
        actor_user_id: str,
        employee_id: str,
        data: EmploymentContractCreate,
    ) -> EmploymentContract:
        employee = await self.get_employee(organization_id, employee_id)
        overlaps = await self.contracts.has_overlap(
            organization_id, employee.id, data.start_date, data.end_date
        )
        try:
            PayrollLifecycleRules.validate_non_overlapping_contract(
                data.start_date, data.end_date, overlaps
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        try:
            contract = await self.contracts.create(organization_id, employee.id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "CONTRACT_CREATED",
                "EmploymentContract",
                contract.id,
                new_value=json.dumps({"contract_number": contract.contract_number}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll contract number already exists",
            ) from exc
        await self.session.refresh(contract)
        return contract

    async def list_contracts(
        self, organization_id: str, employee_id: str
    ) -> list[EmploymentContract]:
        await self.get_employee(organization_id, employee_id)
        return await self.contracts.list_for_employee(organization_id, employee_id)

    async def update_contract(
        self,
        organization_id: str,
        actor_user_id: str,
        contract_id: str,
        data: EmploymentContractUpdate,
    ) -> EmploymentContract:
        contract = await self.contracts.get_by_id(organization_id, contract_id, True)
        if contract is None:
            raise HTTPException(status_code=404, detail="Payroll contract not found")
        start_date = contract.start_date
        end_date = (
            data.end_date if "end_date" in data.model_fields_set else contract.end_date
        )
        overlaps = await self.contracts.has_overlap(
            organization_id, contract.employee_id, start_date, end_date, contract.id
        )
        try:
            PayrollLifecycleRules.validate_non_overlapping_contract(
                start_date, end_date, overlaps
            )
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        previous = {field: getattr(contract, field) for field in data.model_fields_set}
        await self.contracts.update(contract, data)
        await self.audit.append(
            organization_id,
            actor_user_id,
            "CONTRACT_UPDATED",
            "EmploymentContract",
            contract.id,
            previous_value=json.dumps(previous, default=str),
            new_value=json.dumps(data.model_dump(exclude_unset=True), default=str),
        )
        await self.session.commit()
        return await self.contracts.get_by_id(organization_id, contract.id)  # type: ignore[return-value]
