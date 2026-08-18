from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.analytical import (
    AnalyticalDimension,
    AnalyticalDimensionValue,
    JournalEntryLineAnalyticAllocation,
)
from app.models.accounting.budget import Budget, BudgetLine
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.schemas.accounting.analytical import (
    AnalyticalActualResponse,
    AnalyticalAllocationCreate,
    AnalyticalDimensionCreate,
    AnalyticalDimensionValueCreate,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


class AnalyticalService:
    """Configuration and read-only analysis above immutable POSTED ledger lines."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def create_dimension(
        self, organization_id: str, actor_user_id: str, data: AnalyticalDimensionCreate
    ) -> AnalyticalDimension:
        dimension = AnalyticalDimension(
            organization_id=organization_id,
            code=data.code,
            name=data.name,
            is_active="true",
        )
        self.session.add(dimension)
        try:
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "ANALYTICAL_DIMENSION_CREATED",
                "AnalyticalDimension",
                dimension.id,
                new_value={"code": data.code, "name": data.name},
            )
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analytical dimension code already exists",
            )
        return dimension

    async def create_value(
        self,
        organization_id: str,
        actor_user_id: str,
        dimension_id: str,
        data: AnalyticalDimensionValueCreate,
    ) -> AnalyticalDimensionValue:
        dimension = await self.session.scalar(
            select(AnalyticalDimension).where(
                AnalyticalDimension.organization_id == organization_id,
                AnalyticalDimension.id == dimension_id,
                AnalyticalDimension.is_active == "true",
            )
        )
        if dimension is None:
            raise HTTPException(
                status_code=404, detail="Analytical dimension not found"
            )
        value = AnalyticalDimensionValue(
            organization_id=organization_id,
            dimension_id=dimension.id,
            code=data.code,
            label=data.label,
            is_active="true",
        )
        self.session.add(value)
        try:
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "ANALYTICAL_DIMENSION_VALUE_CREATED",
                "AnalyticalDimensionValue",
                value.id,
                new_value={"dimension_id": dimension.id, "code": data.code},
            )
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analytical dimension value code already exists",
            )
        return value

    async def allocate_posted_line(
        self, organization_id: str, actor_user_id: str, data: AnalyticalAllocationCreate
    ) -> JournalEntryLineAnalyticAllocation:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"analytical:{organization_id}:{data.journal_entry_line_id}"},
        )
        line = await self.session.scalar(
            select(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.organization_id == organization_id,
                JournalEntryLine.id == data.journal_entry_line_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
        )
        if line is None:
            raise HTTPException(
                status_code=422,
                detail="Only an existing POSTED journal line can receive analytics",
            )
        if data.amount <= 0:
            raise HTTPException(
                status_code=422, detail="Analytical allocation amount must be positive"
            )
        value = await self.session.scalar(
            select(AnalyticalDimensionValue).where(
                AnalyticalDimensionValue.organization_id == organization_id,
                AnalyticalDimensionValue.id == data.dimension_value_id,
                AnalyticalDimensionValue.dimension_id == data.dimension_id,
                AnalyticalDimensionValue.is_active == "true",
            )
        )
        if value is None:
            raise HTTPException(
                status_code=422,
                detail="Analytical dimension value is not valid for this organization and dimension",
            )
        existing = await self.session.scalar(
            select(JournalEntryLineAnalyticAllocation).where(
                JournalEntryLineAnalyticAllocation.organization_id == organization_id,
                JournalEntryLineAnalyticAllocation.idempotency_key
                == data.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        allocated = await self.session.scalar(
            select(
                func.coalesce(func.sum(JournalEntryLineAnalyticAllocation.amount), 0)
            ).where(
                JournalEntryLineAnalyticAllocation.organization_id == organization_id,
                JournalEntryLineAnalyticAllocation.journal_entry_line_id == line.id,
                JournalEntryLineAnalyticAllocation.dimension_id == data.dimension_id,
            )
        )
        line_amount = Decimal(line.debit or 0) + Decimal(line.credit or 0)
        if Decimal(allocated or 0) + data.amount > line_amount:
            raise HTTPException(
                status_code=409,
                detail="Analytical allocations cannot exceed the posted line amount",
            )
        allocation = JournalEntryLineAnalyticAllocation(
            organization_id=organization_id,
            journal_entry_line_id=line.id,
            dimension_id=data.dimension_id,
            dimension_value_id=value.id,
            amount=data.amount,
            idempotency_key=data.idempotency_key,
            created_by_user_id=actor_user_id,
        )
        self.session.add(allocation)
        try:
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "ANALYTICAL_LINE_ALLOCATED",
                "JournalEntryLineAnalyticAllocation",
                allocation.id,
                new_value={
                    "line_id": line.id,
                    "dimension_id": data.dimension_id,
                    "dimension_value_id": value.id,
                    "amount": str(data.amount),
                },
            )
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(JournalEntryLineAnalyticAllocation).where(
                    JournalEntryLineAnalyticAllocation.organization_id
                    == organization_id,
                    JournalEntryLineAnalyticAllocation.idempotency_key
                    == data.idempotency_key,
                )
            )
            if existing is not None:
                return existing
            raise
        return allocation

    async def actuals(
        self,
        organization_id: str,
        *,
        dimension_id: str | None = None,
        dimension_value_id: str | None = None,
        fiscal_period_id: str | None = None,
        account_id: str | None = None,
    ) -> list[AnalyticalActualResponse]:
        query = (
            select(
                JournalEntryLineAnalyticAllocation.dimension_id,
                JournalEntryLineAnalyticAllocation.dimension_value_id,
                JournalEntryLine.account_id,
                JournalEntry.fiscal_period_id,
                func.sum(JournalEntryLineAnalyticAllocation.amount).label(
                    "allocated_amount"
                ),
                func.sum(
                    func.abs(JournalEntryLine.debit - JournalEntryLine.credit)
                ).label("ledger_amount"),
            )
            .join(
                JournalEntryLine,
                JournalEntryLine.id
                == JournalEntryLineAnalyticAllocation.journal_entry_line_id,
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLineAnalyticAllocation.organization_id == organization_id,
                JournalEntryLine.organization_id == organization_id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .group_by(
                JournalEntryLineAnalyticAllocation.dimension_id,
                JournalEntryLineAnalyticAllocation.dimension_value_id,
                JournalEntryLine.account_id,
                JournalEntry.fiscal_period_id,
            )
        )
        if dimension_id:
            query = query.where(
                JournalEntryLineAnalyticAllocation.dimension_id == dimension_id
            )
        if dimension_value_id:
            query = query.where(
                JournalEntryLineAnalyticAllocation.dimension_value_id
                == dimension_value_id
            )
        if fiscal_period_id:
            query = query.where(JournalEntry.fiscal_period_id == fiscal_period_id)
        if account_id:
            query = query.where(JournalEntryLine.account_id == account_id)
        rows = await self.session.execute(query)
        result = []
        for row in rows:
            allocated = Decimal(row.allocated_amount or 0)
            ledger = Decimal(row.ledger_amount or 0)
            budget = await self.session.scalar(
                select(func.coalesce(func.sum(BudgetLine.amount), 0))
                .join(Budget, Budget.id == BudgetLine.budget_id)
                .where(
                    BudgetLine.organization_id == organization_id,
                    BudgetLine.fiscal_period_id == row.fiscal_period_id,
                    BudgetLine.account_id == row.account_id,
                    BudgetLine.dimension_value_id == row.dimension_value_id,
                    Budget.organization_id == organization_id,
                    Budget.status.in_(("APPROVED", "LOCKED")),
                )
            )
            budget_amount = Decimal(budget) if budget is not None else None
            budget_variance = (
                budget_amount - allocated if budget_amount is not None else None
            )
            result.append(
                AnalyticalActualResponse(
                    dimension_id=row.dimension_id,
                    dimension_value_id=row.dimension_value_id,
                    account_id=row.account_id,
                    fiscal_period_id=row.fiscal_period_id,
                    allocated_amount=allocated,
                    ledger_amount=ledger,
                    variance_to_ledger=allocated - ledger,
                    budget_amount=budget_amount,
                    budget_variance=budget_variance,
                )
            )
        return result
