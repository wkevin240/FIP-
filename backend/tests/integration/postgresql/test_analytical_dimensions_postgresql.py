import os
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.schemas.accounting.analytical import (
    AnalyticalAllocationCreate,
    AnalyticalDimensionCreate,
    AnalyticalDimensionValueCreate,
)
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.analytical_service import AnalyticalService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.accounting.test_bank_reconciliation_service import (
    _create_posted_entry,
    _create_reconciliation_context,
)

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
async def test_analytical_allocation_reconciles_to_posted_ledger(
    postgres_session: AsyncSession,
):
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(postgres_session)
    period_start = period.start_date
    entry_id = await _create_posted_entry(
        postgres_session,
        organization.id,
        period.id,
        journal_id,
        f"AN-{uuid4().hex[:8]}",
        period_start,
        [
            JournalEntryLineCreate(
                account_id=accounts["expense"].id,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
                description="Analytical expense",
            ),
            JournalEntryLineCreate(
                account_id=accounts["bank"].id,
                debit=Decimal("0.00"),
                credit=Decimal("100.00"),
                description="Analytical bank",
            ),
        ],
    )
    line_id = await postgres_session.scalar(
        select(JournalEntryLine.id).where(
            JournalEntryLine.organization_id == organization.id,
            JournalEntryLine.journal_entry_id == entry_id,
            JournalEntryLine.account_id == accounts["expense"].id,
        )
    )
    service = AnalyticalService(postgres_session)
    dimension = await service.create_dimension(
        organization.id,
        user.id,
        AnalyticalDimensionCreate(code=f"COST-{uuid4().hex[:8]}", name="Cost center"),
    )
    value = await service.create_value(
        organization.id,
        user.id,
        dimension.id,
        AnalyticalDimensionValueCreate(code="OPS", label="Operations"),
    )
    allocation = await service.allocate_posted_line(
        organization.id,
        user.id,
        AnalyticalAllocationCreate(
            journal_entry_line_id=line_id,
            dimension_id=dimension.id,
            dimension_value_id=value.id,
            amount=Decimal("100.00"),
            idempotency_key=f"alloc-{uuid4().hex}",
        ),
    )
    again = await service.allocate_posted_line(
        organization.id,
        user.id,
        AnalyticalAllocationCreate(
            journal_entry_line_id=line_id,
            dimension_id=dimension.id,
            dimension_value_id=value.id,
            amount=Decimal("100.00"),
            idempotency_key=allocation.idempotency_key,
        ),
    )
    assert again.id == allocation.id
    report = await service.actuals(
        organization.id,
        dimension_id=dimension.id,
        dimension_value_id=value.id,
        fiscal_period_id=period.id,
        account_id=accounts["expense"].id,
    )
    assert len(report) == 1
    assert report[0].allocated_amount == Decimal("100.00")
    assert report[0].ledger_amount == Decimal("100.00")
    assert report[0].variance_to_ledger == Decimal("0.00")
    with pytest.raises(HTTPException):
        await service.allocate_posted_line(
            organization.id,
            user.id,
            AnalyticalAllocationCreate(
                journal_entry_line_id=line_id,
                dimension_id=dimension.id,
                dimension_value_id=value.id,
                amount=Decimal("0.01"),
                idempotency_key=f"overflow-{uuid4().hex}",
            ),
        )
