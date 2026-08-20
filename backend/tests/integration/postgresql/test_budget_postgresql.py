import os
from uuid import uuid4

import pytest
from app.models.user import User
from app.schemas.accounting.budget import BudgetCreate, BudgetLineCreate
from app.services.accounting.budget_service import BudgetService
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.treasury.test_treasury_accounting_service import _context

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


async def _actor(session: AsyncSession) -> User:
    actor = User(
        email=f"budget-{uuid4().hex[:12]}@test.local",
        full_name="Budget test actor",
        hashed_password="not-used-in-integration-test",
        is_active=True,
        is_superuser=False,
    )
    session.add(actor)
    await session.commit()
    return actor


@pytest.mark.asyncio
async def test_postgresql_budget_is_tenant_scoped_and_approved_only_with_lines(
    postgres_session: AsyncSession,
):
    organization, period, _, _, expense, _ = await _context(postgres_session)
    period_id = period.id
    fiscal_year_id = period.fiscal_year_id
    expense_id = expense.id
    actor = await _actor(postgres_session)
    service = BudgetService(postgres_session)
    budget = await service.create_budget(
        organization.id,
        actor.id,
        BudgetCreate(name=f"Budget {uuid4().hex[:8]}", fiscal_year_id=fiscal_year_id),
    )
    budget_id = budget.id
    line = await service.add_line(
        organization.id,
        actor.id,
        budget_id,
        BudgetLineCreate(
            fiscal_period_id=period_id, account_id=expense_id, amount="1000.00"
        ),
    )
    await service.approve(organization.id, actor.id, budget_id)
    assert line.budget_id == budget_id
    variance = await service.variance(organization.id, budget_id)
    assert variance[0].budget_amount == 1000
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO budget_lines
                (id, created_at, updated_at, organization_id, budget_id,
                 fiscal_period_id, account_id, amount)
                VALUES (:id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :org,
                        :budget, :period, :account, 1.00)
                """
            ),
            {
                "id": uuid4().hex,
                "org": organization.id,
                "budget": budget_id,
                "period": period_id,
                "account": expense_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()
    other_org, other_period, _, _, _, _ = await _context(postgres_session)
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO budget_lines
                (id, created_at, updated_at, organization_id, budget_id,
                 fiscal_period_id, account_id, amount)
                VALUES (:id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :org,
                        :budget, :period, :account, 1.00)
                """
            ),
            {
                "id": uuid4().hex,
                "org": other_org.id,
                "budget": budget_id,
                "period": other_period.id,
                "account": expense_id,
            },
        )
        await postgres_session.commit()
