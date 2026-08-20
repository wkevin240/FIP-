from decimal import ROUND_HALF_UP, Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.schemas.accounting.kpi import KPIMetricResponse, KPIResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class KPIService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate(
        self, organization_id: str, fiscal_period_id: str | None = None
    ) -> KPIResponse:
        if fiscal_period_id:
            period = await self.session.scalar(
                select(FiscalPeriod.id).where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.id == fiscal_period_id,
                )
            )
            if period is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Fiscal period not found")
        query = (
            select(
                Account.account_type,
                func.sum(JournalEntryLine.debit),
                func.sum(JournalEntryLine.credit),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                Account.organization_id == organization_id,
                JournalEntryLine.organization_id == organization_id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .group_by(Account.account_type)
        )
        if fiscal_period_id:
            query = query.where(JournalEntry.fiscal_period_id == fiscal_period_id)
        rows = await self.session.execute(query)
        balances: dict[str, Decimal] = {}
        for account_type, debit, credit in rows:
            debit_amount = Decimal(debit or 0)
            credit_amount = Decimal(credit or 0)
            if account_type in {"REVENUE", "LIABILITY", "EQUITY"}:
                balances[account_type] = (credit_amount - debit_amount).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
            else:
                balances[account_type] = (debit_amount - credit_amount).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
        revenue = balances.get("REVENUE", Decimal("0.00"))
        expenses = balances.get("EXPENSE", Decimal("0.00"))
        net_income = revenue - expenses
        metrics = [
            KPIMetricResponse(
                code="REVENUE",
                label="Produits",
                status="READY" if "REVENUE" in balances else "INCOMPLETE",
                value=revenue,
                unit="amount",
                reason=None
                if "REVENUE" in balances
                else "No POSTED revenue account movement in the selected scope",
            ),
            KPIMetricResponse(
                code="EXPENSES",
                label="Charges",
                status="READY" if "EXPENSE" in balances else "INCOMPLETE",
                value=expenses,
                unit="amount",
                reason=None
                if "EXPENSE" in balances
                else "No POSTED expense account movement in the selected scope",
            ),
            KPIMetricResponse(
                code="NET_INCOME",
                label="Résultat net comptable",
                status="READY" if revenue or expenses else "INCOMPLETE",
                value=net_income,
                unit="amount",
                reason=None
                if revenue or expenses
                else "No POSTED income statement movement in the selected scope",
            ),
            KPIMetricResponse(
                code="NET_MARGIN",
                label="Marge nette",
                status="READY" if revenue else "NOT_READY",
                value=((net_income / revenue) * Decimal("100.00")).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                if revenue
                else None,
                unit="percent",
                reason=None if revenue else "Revenue denominator is absent or zero",
            ),
        ]
        unavailable_reason = "No organization-level account mapping distinguishes the requested KPI components"
        metrics.extend(
            [
                KPIMetricResponse(
                    code="EBITDA",
                    label="EBITDA",
                    status="NOT_READY",
                    unit="amount",
                    reason=unavailable_reason,
                ),
                KPIMetricResponse(
                    code="GROSS_MARGIN",
                    label="Marge brute",
                    status="NOT_READY",
                    unit="percent",
                    reason=unavailable_reason,
                ),
                KPIMetricResponse(
                    code="DSO",
                    label="Délai moyen de recouvrement",
                    status="NOT_READY",
                    unit="days",
                    reason="Customer receivables and revenue mappings are not configured",
                ),
                KPIMetricResponse(
                    code="DPO",
                    label="Délai moyen de paiement fournisseur",
                    status="NOT_READY",
                    unit="days",
                    reason="Supplier payables and purchases mappings are not configured",
                ),
            ]
        )
        overall = (
            "READY"
            if any(metric.status == "READY" for metric in metrics)
            else "NOT_READY"
        )
        return KPIResponse(
            organization_id=organization_id,
            fiscal_period_id=fiscal_period_id,
            status=overall,
            metrics=metrics,
        )
