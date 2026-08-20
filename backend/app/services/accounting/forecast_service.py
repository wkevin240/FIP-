from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.budget import Budget, BudgetLine
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.accounting.scenario import Scenario, ScenarioAssumption
from app.schemas.accounting.forecast import ForecastLineResponse, ForecastResponse
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ForecastService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate(
        self, organization_id: str, budget_id: str, scenario_id: str
    ) -> ForecastResponse:
        budget = await self.session.scalar(
            select(Budget).where(
                Budget.organization_id == organization_id, Budget.id == budget_id
            )
        )
        if budget is None:
            raise HTTPException(status_code=404, detail="Budget not found")
        if budget.status not in {"APPROVED", "LOCKED"}:
            return ForecastResponse(
                budget_id=budget.id,
                scenario_id=scenario_id,
                status="NOT_READY",
                lines=[],
            )
        scenario = await self.session.scalar(
            select(Scenario).where(
                Scenario.organization_id == organization_id,
                Scenario.id == scenario_id,
                Scenario.fiscal_year_id == budget.fiscal_year_id,
            )
        )
        if scenario is None:
            raise HTTPException(
                status_code=404,
                detail="Approved scenario not found for budget fiscal year",
            )
        if scenario.status not in {"APPROVED", "LOCKED"}:
            return ForecastResponse(
                budget_id=budget.id,
                scenario_id=scenario.id,
                status="NOT_READY",
                lines=[],
            )
        budget_lines = list(
            await self.session.scalars(
                select(BudgetLine)
                .where(
                    BudgetLine.organization_id == organization_id,
                    BudgetLine.budget_id == budget.id,
                )
                .order_by(
                    BudgetLine.fiscal_period_id,
                    BudgetLine.account_id,
                    BudgetLine.dimension_value_id,
                )
            )
        )
        if not budget_lines:
            return ForecastResponse(
                budget_id=budget.id,
                scenario_id=scenario.id,
                status="INCOMPLETE",
                lines=[],
            )
        assumptions = list(
            await self.session.scalars(
                select(ScenarioAssumption).where(
                    ScenarioAssumption.organization_id == organization_id,
                    ScenarioAssumption.scenario_id == scenario.id,
                )
            )
        )
        assumption_map = {
            (a.fiscal_period_id, a.account_id, a.dimension_value_id): Decimal(a.amount)
            for a in assumptions
        }
        lines: list[ForecastLineResponse] = []
        for line in budget_lines:
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
            budget_amount = Decimal(line.amount)
            assumption_amount = assumption_map.get(
                (line.fiscal_period_id, line.account_id, line.dimension_value_id),
                Decimal("0.00"),
            )
            lines.append(
                ForecastLineResponse(
                    budget_id=budget.id,
                    scenario_id=scenario.id,
                    fiscal_period_id=line.fiscal_period_id,
                    account_id=line.account_id,
                    dimension_value_id=line.dimension_value_id,
                    actual_amount=actual_amount,
                    approved_budget_amount=budget_amount,
                    scenario_assumption_amount=assumption_amount,
                    forecast_amount=actual_amount + budget_amount + assumption_amount,
                    status="READY",
                )
            )
        return ForecastResponse(
            budget_id=budget.id, scenario_id=scenario.id, status="READY", lines=lines
        )
