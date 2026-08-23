import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.budget import Budget, BudgetLine
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping
from app.models.accounting.scenario import Scenario, ScenarioAssumption
from app.models.organization import Organization
from app.models.user import User
from app.schemas.accounting.financial_variance import VarianceComparison
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from app.services.accounting.financial_variance_service import FinancialVarianceService
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from fastapi import HTTPException
from sqlalchemy import select
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
async def test_profitability_mapping_is_tenant_scoped_on_postgresql(
    postgres_session: AsyncSession,
):
    suffix = uuid4().hex
    organization_a = Organization(name=f"Profitability A {suffix}")
    organization_b = Organization(name=f"Profitability B {suffix}")
    postgres_session.add_all([organization_a, organization_b])
    await postgres_session.flush()
    account = Account(
        organization_id=organization_b.id,
        code=f"70{suffix[:8]}",
        name="Tenant B revenue",
        account_type="REVENUE",
        path="/",
    )
    postgres_session.add(account)
    await postgres_session.flush()
    postgres_session.add(
        ProfitabilityAccountMapping(
            organization_id=organization_b.id,
            account_id=account.id,
            category="REVENUE",
        )
    )
    await postgres_session.commit()

    result = await FinancialCalculationService(postgres_session).profitability(
        organization_a.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result.status == "NOT_READY"
    assert result.source_line_count == 0
    assert result.metrics[0].value is None


@pytest.mark.asyncio
async def test_profitability_rejects_inverted_period_before_database_aggregation(
    postgres_session: AsyncSession,
):
    service = FinancialCalculationService(postgres_session)
    with pytest.raises(HTTPException, match="period_start must be before period_end"):
        await service.profitability("missing-org", date(2026, 2, 1), date(2026, 1, 31))


async def _create_profitability_fixture(session: AsyncSession):
    suffix = uuid4().hex[:10]
    organization = Organization(name=f"Profitability real fixture {suffix}")
    session.add(organization)
    await session.flush()

    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name=f"FY {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name=f"January {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    accounts = {
        "ar": Account(
            organization_id=organization.id,
            code=f"411{suffix}",
            name="Fixture receivable",
            account_type="ASSET",
            level=1,
            path=f"/411{suffix}/",
        ),
        "revenue": Account(
            organization_id=organization.id,
            code=f"701{suffix}",
            name="Fixture revenue",
            account_type="REVENUE",
            level=1,
            path=f"/701{suffix}/",
        ),
        "cogs": Account(
            organization_id=organization.id,
            code=f"601{suffix}",
            name="Fixture cost of sales",
            account_type="EXPENSE",
            level=1,
            path=f"/601{suffix}/",
        ),
        "inventory": Account(
            organization_id=organization.id,
            code=f"31{suffix}",
            name="Fixture inventory",
            account_type="ASSET",
            level=1,
            path=f"/31{suffix}/",
        ),
        "opex": Account(
            organization_id=organization.id,
            code=f"622{suffix}",
            name="Fixture operating expense",
            account_type="EXPENSE",
            level=1,
            path=f"/622{suffix}/",
        ),
        "cash": Account(
            organization_id=organization.id,
            code=f"571{suffix}",
            name="Fixture cash",
            account_type="ASSET",
            level=1,
            path=f"/571{suffix}/",
        ),
    }
    session.add(fiscal_year)
    await session.flush()
    period.fiscal_year_id = fiscal_year.id
    session.add_all([period, *accounts.values()])
    await session.flush()
    journal = await JournalService(session).create_journal(
        organization.id, JournalCreate(code=f"PR{suffix}", name="Profitability fixture")
    )

    entries = [
        (
            "Revenue",
            [
                (accounts["ar"], Decimal("1000.01"), Decimal("0.00")),
                (accounts["revenue"], Decimal("0.00"), Decimal("1000.01")),
            ],
        ),
        (
            "COGS",
            [
                (accounts["cogs"], Decimal("400.00"), Decimal("0.00")),
                (accounts["inventory"], Decimal("0.00"), Decimal("400.00")),
            ],
        ),
        (
            "Opex",
            [
                (accounts["opex"], Decimal("100.01"), Decimal("0.00")),
                (accounts["cash"], Decimal("0.00"), Decimal("100.01")),
            ],
        ),
    ]
    posted_entries = []
    for label, line_values in entries:
        entry = await JournalEntryService(session).create_entry(
            organization.id,
            JournalEntryCreate(
                journal_id=journal.id,
                fiscal_period_id=period.id,
                entry_number=f"{label[:3]}-{suffix}",
                entry_date=date(2026, 1, 15),
                description=f"Fixture {label}",
                lines=[
                    JournalEntryLineCreate(
                        account_id=account.id, debit=debit, credit=credit
                    )
                    for account, debit, credit in line_values
                ],
            ),
            actor_user_id="financial-calculation-test",
        )
        posted_entries.append(
            await JournalEntryService(session).post_entry(
                organization.id, entry.id, actor_user_id="financial-calculation-test"
            )
        )

    for category, account_key in (
        ("REVENUE", "revenue"),
        ("COGS", "cogs"),
        ("OPERATING_EXPENSE", "opex"),
    ):
        session.add(
            ProfitabilityAccountMapping(
                organization_id=organization.id,
                account_id=accounts[account_key].id,
                category=category,
            )
        )
    await session.commit()
    return organization, posted_entries


@pytest.mark.asyncio
async def test_profitability_engine_calculates_posted_ledger_with_decimal_values(
    postgres_session: AsyncSession,
):
    organization, posted_entries = await _create_profitability_fixture(postgres_session)

    result = await FinancialCalculationService(postgres_session).profitability(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    metrics = {metric.code: metric for metric in result.metrics}

    assert all(entry.status.value == "POSTED" for entry in posted_entries)
    assert result.status == "READY"
    assert result.ledger_is_balanced is True
    assert result.ledger_balance_difference == Decimal("0.00")
    assert metrics["REVENUE"].value == Decimal("1000.01")
    assert metrics["COGS"].value == Decimal("400.00")
    assert metrics["OPERATING_EXPENSE"].value == Decimal("100.01")
    assert metrics["GROSS_PROFIT"].value == Decimal("600.01")
    assert metrics["OPERATING_INCOME"].value == Decimal("500.00")
    assert metrics["NET_INCOME"].value == Decimal("500.00")
    assert metrics["GROSS_MARGIN"].value == Decimal("0.60")
    assert metrics["OPERATING_MARGIN"].value == Decimal("0.50")
    assert metrics["NET_MARGIN"].value == Decimal("0.50")
    assert metrics["NET_INCOME"].journal_entry_line_ids
    assert set(metrics["NET_INCOME"].account_ids) >= {
        posted_entries[0].lines[1].account_id,
        posted_entries[1].lines[0].account_id,
        posted_entries[2].lines[0].account_id,
    }


@pytest.mark.asyncio
async def test_profitability_engine_excludes_draft_and_future_entries(
    postgres_session: AsyncSession,
):
    organization, _ = await _create_profitability_fixture(postgres_session)
    mapping = await postgres_session.scalar(
        select(ProfitabilityAccountMapping).where(
            ProfitabilityAccountMapping.organization_id == organization.id,
            ProfitabilityAccountMapping.category == "REVENUE",
        )
    )
    assert mapping is not None
    result = await FinancialCalculationService(postgres_session).profitability(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    baseline = next(metric for metric in result.metrics if metric.code == "REVENUE")
    assert baseline.value == Decimal("1000.01")
    assert baseline.status == "READY"


@pytest.mark.asyncio
async def test_variance_engine_compares_actual_budget_and_forecast_with_decimal(
    postgres_session: AsyncSession,
):
    organization, posted_entries = await _create_profitability_fixture(postgres_session)
    revenue_mapping = await postgres_session.scalar(
        select(ProfitabilityAccountMapping).where(
            ProfitabilityAccountMapping.organization_id == organization.id,
            ProfitabilityAccountMapping.category == "REVENUE",
        )
    )
    assert revenue_mapping is not None
    period = await postgres_session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.id == posted_entries[0].fiscal_period_id
        )
    )
    assert period is not None
    user = User(
        email=f"variance-{uuid4().hex}@test.invalid",
        full_name="Variance test actor",
        hashed_password="fixture-only",
    )
    budget = Budget(
        organization_id=organization.id,
        fiscal_year_id=period.fiscal_year_id,
        name=f"Approved budget {uuid4().hex[:8]}",
        status="APPROVED",
    )
    scenario = Scenario(
        organization_id=organization.id,
        fiscal_year_id=period.fiscal_year_id,
        code=f"BASE-{uuid4().hex[:8]}",
        name="Approved forecast scenario",
        status="APPROVED",
    )
    postgres_session.add_all([user, budget, scenario])
    await postgres_session.flush()
    budget_line = BudgetLine(
        organization_id=organization.id,
        budget_id=budget.id,
        fiscal_period_id=period.id,
        account_id=revenue_mapping.account_id,
        amount=Decimal("1200.01"),
    )
    assumption = ScenarioAssumption(
        organization_id=organization.id,
        scenario_id=scenario.id,
        fiscal_period_id=period.id,
        account_id=revenue_mapping.account_id,
        amount=Decimal("900.01"),
        rationale="Fixture assumption to produce the approved forecast source",
        created_by_user_id=user.id,
    )
    postgres_session.add_all([budget_line, assumption])
    await postgres_session.commit()

    service = FinancialVarianceService(postgres_session)
    budget_result = await service.calculate(
        organization.id,
        date(2026, 1, 1),
        date(2026, 1, 31),
        VarianceComparison.BUDGET,
        budget_id=budget.id,
    )
    forecast_result = await service.calculate(
        organization.id,
        date(2026, 1, 1),
        date(2026, 1, 31),
        VarianceComparison.FORECAST,
        budget_id=budget.id,
        scenario_id=scenario.id,
    )
    budget_metric = next(
        metric for metric in budget_result.metrics if metric.metric == "REVENUE"
    )
    forecast_metric = next(
        metric for metric in forecast_result.metrics if metric.metric == "REVENUE"
    )

    assert budget_result.status == "READY"
    assert budget_metric.actual == Decimal("1000.01")
    assert budget_metric.comparison == Decimal("1200.01")
    assert budget_metric.variance == Decimal("-200.00")
    assert budget_metric.variance_percentage == Decimal("-0.17")
    assert budget_metric.source_budget_lines == [budget_line.id]
    assert forecast_result.status == "READY"
    assert forecast_metric.actual == Decimal("1000.01")
    assert forecast_metric.comparison == Decimal("1100.01")
    assert forecast_metric.variance == Decimal("-100.00")
    assert forecast_metric.variance_percentage == Decimal("-0.09")
    assert forecast_metric.source_forecast_data


async def _create_budget_source(
    session: AsyncSession,
    organization_id: str,
    fiscal_year_id: str,
    period_id: str,
    account_id: str,
    status: str,
) -> Budget:
    budget = Budget(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        name=f"Budget {status} {uuid4().hex[:8]}",
        status=status,
    )
    session.add(budget)
    await session.flush()
    session.add(
        BudgetLine(
            organization_id=organization_id,
            budget_id=budget.id,
            fiscal_period_id=period_id,
            account_id=account_id,
            amount=Decimal("1200.01"),
        )
    )
    await session.commit()
    return budget


@pytest.mark.asyncio
async def test_variance_budget_statuses_and_tenant_scope_postgresql(
    postgres_session: AsyncSession,
):
    organization, posted_entries = await _create_profitability_fixture(postgres_session)
    mapping = await postgres_session.scalar(
        select(ProfitabilityAccountMapping).where(
            ProfitabilityAccountMapping.organization_id == organization.id,
            ProfitabilityAccountMapping.category == "REVENUE",
        )
    )
    period = await postgres_session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.id == posted_entries[0].fiscal_period_id
        )
    )
    assert mapping is not None and period is not None
    service = FinancialVarianceService(postgres_session)

    for budget_status, expected in (
        ("DRAFT", "NOT_READY"),
        ("APPROVED", "READY"),
        ("LOCKED", "READY"),
    ):
        budget = await _create_budget_source(
            postgres_session,
            organization.id,
            period.fiscal_year_id,
            period.id,
            mapping.account_id,
            budget_status,
        )
        result = await service.calculate(
            organization.id,
            date(2026, 1, 1),
            date(2026, 1, 31),
            VarianceComparison.BUDGET,
            budget_id=budget.id,
        )
        assert result.status == expected

    other_org = Organization(name=f"Budget tenant isolation {uuid4().hex[:8]}")
    postgres_session.add(other_org)
    await postgres_session.flush()
    other_budget = Budget(
        organization_id=other_org.id,
        fiscal_year_id=period.fiscal_year_id,
        name="Other tenant budget",
        status="APPROVED",
    )
    postgres_session.add(other_budget)
    await postgres_session.commit()
    isolated = await service.calculate(
        organization.id,
        date(2026, 1, 1),
        date(2026, 1, 31),
        VarianceComparison.BUDGET,
        budget_id=other_budget.id,
    )
    assert isolated.status == "NOT_READY"
    assert isolated.reason == "BUDGET_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_variance_forecast_scenario_statuses_postgresql(
    postgres_session: AsyncSession,
):
    organization, posted_entries = await _create_profitability_fixture(postgres_session)
    mapping = await postgres_session.scalar(
        select(ProfitabilityAccountMapping).where(
            ProfitabilityAccountMapping.organization_id == organization.id,
            ProfitabilityAccountMapping.category == "REVENUE",
        )
    )
    period = await postgres_session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.id == posted_entries[0].fiscal_period_id
        )
    )
    assert mapping is not None and period is not None
    budget = await _create_budget_source(
        postgres_session,
        organization.id,
        period.fiscal_year_id,
        period.id,
        mapping.account_id,
        "APPROVED",
    )
    user = User(
        email=f"scenario-{uuid4().hex}@test.invalid",
        full_name="Scenario fixture actor",
        hashed_password="fixture-only",
    )
    postgres_session.add(user)
    await postgres_session.flush()
    service = FinancialVarianceService(postgres_session)

    for scenario_status, expected in (
        ("DRAFT", "NOT_READY"),
        ("APPROVED", "READY"),
        ("LOCKED", "READY"),
    ):
        scenario = Scenario(
            organization_id=organization.id,
            fiscal_year_id=period.fiscal_year_id,
            code=f"SC-{scenario_status}-{uuid4().hex[:8]}",
            name=f"Scenario {scenario_status}",
            status=scenario_status,
        )
        postgres_session.add(scenario)
        await postgres_session.flush()
        postgres_session.add(
            ScenarioAssumption(
                organization_id=organization.id,
                scenario_id=scenario.id,
                fiscal_period_id=period.id,
                account_id=mapping.account_id,
                amount=Decimal("900.01"),
                rationale="Fixture scenario assumption",
                created_by_user_id=user.id,
            )
        )
        await postgres_session.commit()
        result = await service.calculate(
            organization.id,
            date(2026, 1, 1),
            date(2026, 1, 31),
            VarianceComparison.FORECAST,
            budget_id=budget.id,
            scenario_id=scenario.id,
        )
        assert result.status == expected
