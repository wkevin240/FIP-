from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.fiscal_period import FiscalPeriod
from app.schemas.accounting.financial_closing_control import (
    ClosingControlBlocker,
    ClosingControlCheck,
    FinancialClosingControlResponse,
)
from app.services.accounting.closing_readiness_service import ClosingReadinessService
from app.services.accounting.kpi_service import KPIService
from app.services.accounting.reporting_service import ReportingService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class FinancialClosingControlService:
    """Read-only orchestration of the existing financial control services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.readiness = ClosingReadinessService(session)
        self.kpi = KPIService(session)
        self.reporting = ReportingService(session)

    async def assess(
        self,
        organization_id: str,
        fiscal_year_id: str,
        fiscal_period_id: str,
    ) -> FinancialClosingControlResponse:
        period = await self._get_period(
            organization_id, fiscal_year_id, fiscal_period_id
        )
        year_readiness = await self.readiness.assess(organization_id, fiscal_year_id)
        kpis = await self.kpi.calculate(
            organization_id,
            fiscal_period_id=fiscal_period_id,
            period_start=period.start_date,
            period_end=period.end_date,
            as_of=period.end_date,
        )
        trial_balance = await self.reporting.trial_balance(
            organization_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        controls: list[ClosingControlCheck] = []
        controls.append(self._readiness_control(year_readiness))
        controls.append(self._period_control(period))
        controls.extend(self._kpi_controls(kpis))
        controls.append(
            self._reporting_control(
                trial_balance.total_debit,
                trial_balance.total_credit,
                trial_balance.is_balanced,
                [line.account_id for line in trial_balance.lines],
            )
        )
        blockers = [blocker for control in controls for blocker in control.blockers]
        statuses = {control.status for control in controls}
        if "INCOMPLETE" in statuses:
            overall = "INCOMPLETE"
        elif "NOT_READY" in statuses:
            overall = "NOT_READY"
        else:
            overall = "READY"
        return FinancialClosingControlResponse(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            fiscal_period_id=fiscal_period_id,
            period_start=period.start_date,
            period_end=period.end_date,
            status=overall,
            controls=controls,
            blockers=blockers,
        )

    async def _get_period(
        self,
        organization_id: str,
        fiscal_year_id: str,
        fiscal_period_id: str,
    ) -> FiscalPeriod:
        period = await self.session.scalar(
            select(FiscalPeriod)
            .options(selectinload(FiscalPeriod.fiscal_year))
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.fiscal_year_id == fiscal_year_id,
                FiscalPeriod.id == fiscal_period_id,
            )
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fiscal period not found for organization and fiscal year",
            )
        return period

    @staticmethod
    def _blocker(
        code: str,
        module: str,
        description: str,
        source_ids: list[str] | None = None,
        amount: Decimal | None = None,
        severity: str = "ERROR",
    ) -> ClosingControlBlocker:
        return ClosingControlBlocker(
            code=code,
            module=module,
            severity=severity,
            description=description,
            source_ids=source_ids or [],
            amount=amount,
        )

    def _readiness_control(self, readiness) -> ClosingControlCheck:
        blockers = [
            self._blocker(
                code=code,
                module="ACCOUNTING",
                description=f"Closing readiness blocker reported by ClosingReadinessService: {code}",
            )
            for code in readiness.blockers
        ]
        return ClosingControlCheck(
            control_code="CLOSING_READINESS",
            status=readiness.status,
            actual=readiness.status,
            expected="READY",
            blockers=blockers,
        )

    def _period_control(self, period: FiscalPeriod) -> ClosingControlCheck:
        status_value = getattr(period.status, "value", period.status)
        blockers: list[ClosingControlBlocker] = []
        control_status = "READY"
        if status_value != FiscalPeriodStatus.OPEN.value:
            control_status = "NOT_READY"
            blockers.append(
                self._blocker(
                    "FISCAL_PERIOD_NOT_OPEN",
                    "ACCOUNTING",
                    "The requested fiscal period is not open for closing control.",
                    [period.id],
                )
            )
        if period.end_date < period.start_date:
            control_status = "INCOMPLETE"
            blockers.append(
                self._blocker(
                    "INVALID_FISCAL_PERIOD_DATES",
                    "ACCOUNTING",
                    "The fiscal period end date precedes its start date.",
                    [period.id],
                )
            )
        return ClosingControlCheck(
            control_code="FISCAL_PERIOD",
            status=control_status,
            actual=status_value,
            expected=FiscalPeriodStatus.OPEN.value,
            source_ids=[period.id],
            blockers=blockers,
        )

    def _kpi_controls(self, kpis) -> list[ClosingControlCheck]:
        selected = {
            "AR_OUTSTANDING",
            "AP_OUTSTANDING",
            "DSO",
            "DPO",
            "WORKING_CAPITAL",
            "NET_WORKING_CAPITAL",
            "LIQUIDITY",
            "RECONCILIATION",
        }
        controls: list[ClosingControlCheck] = []
        for metric in kpis.metrics:
            if metric.code not in selected:
                continue
            blockers = [
                self._blocker(
                    code=code,
                    module="KPI",
                    description=metric.reason or f"KPI {metric.code} is not ready.",
                    source_ids=metric.source_ids,
                    amount=metric.value,
                )
                for code in metric.blockers
                or ([metric.reason] if metric.reason else [])
            ]
            controls.append(
                ClosingControlCheck(
                    control_code=metric.code,
                    status=metric.status,
                    formula=metric.formula,
                    actual=metric.value,
                    expected="AVAILABLE",
                    source_ids=metric.source_ids,
                    blockers=blockers,
                )
            )
        return controls

    def _reporting_control(
        self,
        debit: Decimal,
        credit: Decimal,
        is_balanced: bool,
        source_ids: list[str],
    ) -> ClosingControlCheck:
        difference = (debit - credit).quantize(Decimal("0.01"))
        blockers: list[ClosingControlBlocker] = []
        status_value = "READY" if is_balanced and source_ids else "NOT_READY"
        if not source_ids:
            blockers.append(
                self._blocker(
                    "REPORTING_SOURCE_ABSENT",
                    "REPORTING",
                    "No POSTED reporting lines exist for the requested period.",
                )
            )
        elif not is_balanced:
            status_value = "INCOMPLETE"
            blockers.append(
                self._blocker(
                    "REPORTING_TRIAL_BALANCE_UNBALANCED",
                    "REPORTING",
                    "Trial balance debit and credit totals differ.",
                    source_ids,
                    difference,
                )
            )
        return ClosingControlCheck(
            control_code="REPORTING_TRIAL_BALANCE",
            status=status_value,
            formula="total_debit - total_credit",
            actual=debit,
            expected=credit,
            difference=difference,
            source_ids=source_ids,
            blockers=blockers,
        )
