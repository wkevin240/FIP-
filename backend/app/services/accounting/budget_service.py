from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.account import Account
from app.models.accounting.budget import Budget, BudgetLine
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.schemas.accounting.budget import (
    BudgetCreate,
    BudgetLineCreate,
    BudgetVarianceResponse,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BudgetService:
    """Tenant-scoped FP&A budgets whose actuals come from the central ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def create_budget(
        self, organization_id: str, actor_user_id: str, data: BudgetCreate
    ) -> Budget:
        year = await self.session.scalar(
            select(func.count()).select_from(
                select(Budget)
                .where(
                    Budget.organization_id == organization_id,
                    Budget.fiscal_year_id == data.fiscal_year_id,
                )
                .subquery()
            )
        )
        if year:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A budget already exists for this fiscal year",
            )
        budget = Budget(
            organization_id=organization_id,
            fiscal_year_id=data.fiscal_year_id,
            name=data.name,
            status="DRAFT",
        )
        self.session.add(budget)
        await self.session.flush()
        await self.audit.record(
            organization_id,
            actor_user_id,
            "BUDGET_CREATED",
            "Budget",
            budget.id,
            new_value={"name": budget.name, "fiscal_year_id": budget.fiscal_year_id},
        )
        await self.session.commit()
        return budget

    async def add_line(
        self,
        organization_id: str,
        actor_user_id: str,
        budget_id: str,
        data: BudgetLineCreate,
    ) -> BudgetLine:
        budget = await self._get_budget(organization_id, budget_id, for_update=True)
        if budget.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only DRAFT budgets can be changed",
            )
        period = await self.session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.id == data.fiscal_period_id,
                FiscalPeriod.fiscal_year_id == budget.fiscal_year_id,
            )
        )
        if period is None:
            raise HTTPException(
                status_code=422,
                detail="Fiscal period does not belong to the budget fiscal year",
            )
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == data.account_id,
            )
        )
        if account is None:
            raise HTTPException(
                status_code=422, detail="Account not found in organization"
            )
        line = BudgetLine(
            organization_id=organization_id,
            budget_id=budget.id,
            fiscal_period_id=period.id,
            account_id=account.id,
            amount=data.amount,
        )
        self.session.add(line)
        try:
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BUDGET_LINE_ADDED",
                "BudgetLine",
                line.id,
                new_value={
                    "budget_id": budget.id,
                    "period_id": period.id,
                    "account_id": account.id,
                    "amount": str(data.amount),
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return line

    async def approve(
        self, organization_id: str, actor_user_id: str, budget_id: str
    ) -> Budget:
        budget = await self._get_budget(organization_id, budget_id, for_update=True)
        if budget.status != "DRAFT":
            if budget.status == "APPROVED":
                return budget
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Locked budget cannot be approved",
            )
        has_line = await self.session.scalar(
            select(BudgetLine.id)
            .where(
                BudgetLine.organization_id == organization_id,
                BudgetLine.budget_id == budget.id,
            )
            .limit(1)
        )
        if has_line is None:
            raise HTTPException(
                status_code=422, detail="A budget requires at least one configured line"
            )
        budget.status = "APPROVED"
        budget.approved_at = datetime.now(timezone.utc)
        budget.approved_by_user_id = actor_user_id
        await self.audit.record(
            organization_id,
            actor_user_id,
            "BUDGET_APPROVED",
            "Budget",
            budget.id,
            new_value={"status": budget.status},
        )
        await self.session.commit()
        return budget

    async def variance(
        self,
        organization_id: str,
        budget_id: str,
        period_id: str | None = None,
        account_id: str | None = None,
    ) -> list[BudgetVarianceResponse]:
        budget = await self._get_budget(organization_id, budget_id)
        if budget.status not in {"APPROVED", "LOCKED"}:
            raise HTTPException(
                status_code=409,
                detail="Budget must be APPROVED before variance analysis",
            )
        query = select(BudgetLine).where(
            BudgetLine.organization_id == organization_id,
            BudgetLine.budget_id == budget.id,
        )
        if period_id:
            query = query.where(BudgetLine.fiscal_period_id == period_id)
        if account_id:
            query = query.where(BudgetLine.account_id == account_id)
        lines = list(
            await self.session.scalars(
                query.order_by(BudgetLine.fiscal_period_id, BudgetLine.account_id)
            )
        )
        result: list[BudgetVarianceResponse] = []
        for line in lines:
            actual = await self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(JournalEntryLine.debit - JournalEntryLine.credit), 0
                    )
                )
                .join(
                    JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
                )
                .where(
                    JournalEntryLine.organization_id == organization_id,
                    JournalEntryLine.account_id == line.account_id,
                    JournalEntry.fiscal_period_id == line.fiscal_period_id,
                    JournalEntry.status == JournalEntryStatus.POSTED,
                )
            )
            actual_amount = Decimal(actual or 0)
            result.append(
                BudgetVarianceResponse(
                    budget_id=budget.id,
                    fiscal_period_id=line.fiscal_period_id,
                    account_id=line.account_id,
                    budget_amount=Decimal(line.amount),
                    actual_amount=actual_amount,
                    variance_amount=Decimal(line.amount) - actual_amount,
                )
            )
        return result

    async def _get_budget(
        self, organization_id: str, budget_id: str, for_update: bool = False
    ) -> Budget:
        query = select(Budget).where(
            Budget.organization_id == organization_id, Budget.id == budget_id
        )
        if for_update:
            query = query.with_for_update()
        budget = await self.session.scalar(query)
        if budget is None:
            raise HTTPException(status_code=404, detail="Budget not found")
        return budget
