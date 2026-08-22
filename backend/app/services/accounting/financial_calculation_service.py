from decimal import ROUND_HALF_UP, Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping
from app.schemas.accounting.financial_calculation import (
    CATEGORIES,
    ProfitabilityMappingCreate,
    ProfitabilityMetric,
    ProfitabilityResponse,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class FinancialCalculationService:
    """Reusable read-only financial calculations over the posted ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def create_mapping(
        self, organization_id: str, actor_user_id: str, data: ProfitabilityMappingCreate
    ) -> ProfitabilityAccountMapping:
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == data.account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active account in the current organization is required",
            )
        if data.category not in CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unsupported profitability category",
            )
        existing = await self.session.scalar(
            select(ProfitabilityAccountMapping).where(
                ProfitabilityAccountMapping.organization_id == organization_id,
                ProfitabilityAccountMapping.account_id == data.account_id,
                ProfitabilityAccountMapping.category == data.category,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="Profitability mapping already exists"
            )
        mapping = ProfitabilityAccountMapping(
            organization_id=organization_id,
            account_id=data.account_id,
            category=data.category,
        )
        self.session.add(mapping)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PROFITABILITY_MAPPING_CREATED",
            resource_type="ProfitabilityAccountMapping",
            resource_id=mapping.id,
            new_value={"account_id": data.account_id, "category": data.category},
        )
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def list_mappings(
        self, organization_id: str
    ) -> list[ProfitabilityAccountMapping]:
        return list(
            await self.session.scalars(
                select(ProfitabilityAccountMapping)
                .where(
                    ProfitabilityAccountMapping.organization_id == organization_id,
                    ProfitabilityAccountMapping.is_active.is_(True),
                )
                .order_by(
                    ProfitabilityAccountMapping.category,
                    ProfitabilityAccountMapping.account_id,
                )
            )
        )

    async def profitability(
        self, organization_id: str, period_start, period_end
    ) -> ProfitabilityResponse:
        if period_start > period_end:
            raise HTTPException(
                status_code=422, detail="period_start must be before period_end"
            )
        mappings = await self.list_mappings(organization_id)
        by_category: dict[str, list[str]] = {category: [] for category in CATEGORIES}
        for mapping in mappings:
            by_category[mapping.category].append(mapping.account_id)
        rows = await self.session.execute(
            select(
                JournalEntryLine.id,
                JournalEntryLine.account_id,
                JournalEntryLine.debit,
                JournalEntryLine.credit,
                ProfitabilityAccountMapping.category,
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(
                ProfitabilityAccountMapping,
                (
                    ProfitabilityAccountMapping.organization_id
                    == JournalEntryLine.organization_id
                )
                & (
                    ProfitabilityAccountMapping.account_id
                    == JournalEntryLine.account_id
                )
                & ProfitabilityAccountMapping.is_active.is_(True),
            )
            .where(
                JournalEntryLine.organization_id == organization_id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
            )
        )
        totals: dict[str, Decimal] = {
            category: Decimal("0.00") for category in CATEGORIES
        }
        source_lines: dict[str, list[str]] = {category: [] for category in CATEGORIES}
        source_accounts: dict[str, set[str]] = {
            category: set() for category in CATEGORIES
        }
        for line_id, account_id, debit, credit, category in rows:
            debit_value = Decimal(debit or 0)
            credit_value = Decimal(credit or 0)
            if category in {"REVENUE", "OTHER_INCOME"}:
                totals[category] += credit_value - debit_value
            else:
                totals[category] += debit_value - credit_value
            source_lines[category].append(line_id)
            source_accounts[category].add(account_id)
        required = ("REVENUE", "COGS", "OPERATING_EXPENSE")
        missing = [category for category in required if not by_category[category]]
        metrics: list[ProfitabilityMetric] = []
        for category in CATEGORIES:
            ready = bool(by_category[category])
            metrics.append(
                ProfitabilityMetric(
                    code=category,
                    value=totals[category].quantize(CENT, rounding=ROUND_HALF_UP)
                    if ready
                    else None,
                    formula=(
                        "credit - debit"
                        if category in {"REVENUE", "OTHER_INCOME"}
                        else "debit - credit"
                    ),
                    status="READY" if ready else "NOT_READY",
                    period_start=period_start,
                    period_end=period_end,
                    account_ids=sorted(source_accounts[category]),
                    journal_entry_line_ids=sorted(source_lines[category]),
                    dimensions=[],
                    reason=None
                    if ready
                    else f"No explicit organization mapping for {category}",
                )
            )
        revenue = totals["REVENUE"] if "REVENUE" not in missing else None
        cogs = totals["COGS"] if "COGS" not in missing else None
        opex = (
            totals["OPERATING_EXPENSE"] if "OPERATING_EXPENSE" not in missing else None
        )
        other_income = totals["OTHER_INCOME"]
        other_expense = totals["OTHER_EXPENSE"]
        derived = {
            "GROSS_PROFIT": (revenue - cogs)
            if revenue is not None and cogs is not None
            else None,
            "OPERATING_INCOME": (revenue - cogs - opex)
            if revenue is not None and cogs is not None and opex is not None
            else None,
            "NET_INCOME": (revenue - cogs - opex + other_income - other_expense)
            if revenue is not None and cogs is not None and opex is not None
            else None,
        }
        derived_formulas = {
            "GROSS_PROFIT": "REVENUE - COGS",
            "OPERATING_INCOME": "REVENUE - COGS - OPERATING_EXPENSE",
            "NET_INCOME": "REVENUE - COGS - OPERATING_EXPENSE + OTHER_INCOME - OTHER_EXPENSE",
        }
        for code, value in derived.items():
            metrics.append(
                ProfitabilityMetric(
                    code=code,
                    value=value.quantize(CENT, rounding=ROUND_HALF_UP)
                    if value is not None
                    else None,
                    formula=derived_formulas[code],
                    status="READY" if value is not None else "NOT_READY",
                    period_start=period_start,
                    period_end=period_end,
                    account_ids=sorted(
                        {
                            account
                            for category in required
                            for account in source_accounts[category]
                        }
                    ),
                    journal_entry_line_ids=sorted(
                        {
                            line
                            for category in required
                            for line in source_lines[category]
                        }
                    ),
                    dimensions=[],
                    reason=None
                    if value is not None
                    else "Revenue, COGS and operating expense mappings are all required",
                )
            )
        balance = await self.session.scalar(
            select(
                func.coalesce(func.sum(JournalEntryLine.debit), 0)
                - func.coalesce(func.sum(JournalEntryLine.credit), 0)
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.organization_id == organization_id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= period_start,
                JournalEntry.entry_date <= period_end,
            )
        )
        return ProfitabilityResponse(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            status="READY" if not missing else "NOT_READY",
            metrics=metrics,
            source_line_count=sum(len(lines) for lines in source_lines.values()),
            ledger_is_balanced=Decimal(balance or 0).quantize(CENT) == Decimal("0.00"),
        )
