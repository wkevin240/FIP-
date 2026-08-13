import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.organization import Organization
from app.models.payroll.employee import Employee, EmploymentContract
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="PostgreSQL integration database is not configured",
)


@pytest.fixture
async def postgres_session():
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_payroll_migration_creates_tables_and_enforces_contract_constraints(
    postgres_session: AsyncSession,
) -> None:
    table_names = await postgres_session.run_sync(
        lambda sync_session: inspect(sync_session.bind).get_table_names()
    )
    assert {
        "payroll_employees",
        "payroll_contracts",
        "payroll_rule_sets",
        "payroll_periods",
        "payroll_slips",
        "payroll_audit_events",
    }.issubset(table_names)

    organization = Organization(
        name=f"PostgreSQL payroll integration organization {uuid4().hex[:12]}"
    )
    postgres_session.add(organization)
    await postgres_session.commit()
    organization_id = organization.id
    employee = Employee(
        organization_id=organization_id,
        employee_code="PG-EMP-001",
        first_name="Postgres",
        last_name="Payroll",
        hire_date=date(2026, 1, 1),
        is_active=True,
    )
    postgres_session.add(employee)
    await postgres_session.commit()
    employee_id = employee.id

    invalid_contract = EmploymentContract(
        organization_id=organization_id,
        employee_id=employee_id,
        contract_number="PG-CON-INVALID",
        title="Invalid amount contract",
        start_date=date(2026, 1, 1),
        base_salary=Decimal("-1.00"),
        currency="XAF",
        status="DRAFT",
    )
    postgres_session.add(invalid_contract)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    valid_contract = EmploymentContract(
        organization_id=organization_id,
        employee_id=employee_id,
        contract_number="PG-CON-001",
        title="Valid contract",
        start_date=date(2026, 1, 1),
        base_salary=Decimal("1000.00"),
        currency="XAF",
        status="ACTIVE",
    )
    postgres_session.add(valid_contract)
    await postgres_session.commit()
    assert valid_contract.id
