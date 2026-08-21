from datetime import date
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import (
    PaymentAllocation,
    SupplierPaymentAllocation,
)
from app.models.procurement import SupplierPayment
from app.models.treasury.bank_account import TreasuryBankAccount
from app.models.treasury.banking_control import BankingControlException
from app.models.treasury.liquidity_alert import LiquidityAlertConfiguration
from app.schemas.accounting.cash_forecast import CashForecastResponse
from app.schemas.treasury.banking_cross_reconciliation import (
    BankingCrossReconciliationResponse,
)
from app.schemas.treasury.liquidity_control import (
    LiquidityAlert,
    LiquidityAlertConfigurationCreate,
    LiquidityAlertsResponse,
    LiquidityControlResponse,
)
from app.services.accounting.cash_forecast_service import CashForecastService
from app.services.audit.audit_service import AuditService
from app.services.treasury.banking_cross_reconciliation_service import (
    BankingCrossReconciliationService,
)
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
THRESHOLD_CODES = {"LOW_LIQUIDITY", "LIQUIDITY_GAP"}


class LiquidityControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.cross = BankingCrossReconciliationService(session)
        self.cash_forecast = CashForecastService(session)

    async def control(
        self,
        organization_id: str,
        actor_user_id: str | None,
        as_of: date,
        horizon_end: date,
    ) -> LiquidityControlResponse:
        if horizon_end < as_of:
            raise HTTPException(
                status_code=422, detail="horizon_end must be on or after as_of"
            )
        cross = await self.cross.report(organization_id, as_of)
        current_cash = await self._current_cash(organization_id, as_of)
        forecast = await self.cash_forecast.calculate(
            organization_id, as_of, horizon_end
        )
        configs = await self._active_configs(organization_id, as_of)
        blockers = list(dict.fromkeys(cross.blockers + forecast.blockers))
        customer_unapplied = await self._customer_unapplied(organization_id, as_of)
        supplier_unapplied = await self._supplier_unapplied(organization_id, as_of)
        forecast_cash = (
            forecast.projected_closing_cash if forecast.status == "READY" else None
        )
        required = self._threshold(configs, "LIQUIDITY_GAP")
        liquidity_gap = (
            (forecast_cash - required).quantize(CENT)
            if forecast_cash is not None and required is not None
            else None
        )
        alerts = self._alerts(
            as_of=as_of,
            horizon_end=horizon_end,
            current_cash=current_cash,
            forecast=forecast,
            cross=cross,
            liquidity_gap=liquidity_gap,
            configs=configs,
        )
        if (
            current_cash is None
            or cross.status != "READY"
            or forecast.status != "READY"
        ):
            overall = "INCOMPLETE"
        else:
            overall = "READY"
        return LiquidityControlResponse(
            organization_id=organization_id,
            as_of=as_of,
            horizon_end=horizon_end,
            status=overall,
            current_cash_position=(current_cash or ZERO).quantize(CENT),
            available_cash=(current_cash or ZERO).quantize(CENT),
            ar_outstanding=cross.ar_outstanding.quantize(CENT),
            ap_outstanding=cross.ap_outstanding.quantize(CENT),
            net_liquidity=(
                (current_cash or ZERO) + cross.ar_outstanding - cross.ap_outstanding
            ).quantize(CENT),
            forecast_cash_position=forecast_cash,
            liquidity_gap=liquidity_gap,
            unresolved_banking_exposure=await self._unresolved_exposure(
                organization_id, as_of
            ),
            unallocated_customer_payments=customer_unapplied,
            unallocated_supplier_payments=supplier_unapplied,
            current_period_blockers=blockers,
            sources={
                "current_cash_position": "TreasuryBankAccount + BankTransaction",
                "banking": "BankingCrossReconciliationService",
                "ar": "BankingCrossReconciliationService",
                "ap": "BankingCrossReconciliationService",
                "forecast": "CashForecastService",
                "unallocated_customer_payments": "Payment + PaymentAllocation",
                "unallocated_supplier_payments": "SupplierPayment + SupplierPaymentAllocation",
            },
            alerts=alerts,
        )

    async def alerts(
        self,
        organization_id: str,
        as_of: date,
        horizon_end: date,
    ) -> LiquidityAlertsResponse:
        report = await self.control(organization_id, None, as_of, horizon_end)
        return LiquidityAlertsResponse(
            organization_id=organization_id,
            as_of=as_of,
            horizon_end=horizon_end,
            status=report.status,
            alerts=report.alerts,
            blockers=report.current_period_blockers,
        )

    async def forecast(
        self, organization_id: str, as_of: date, horizon_end: date
    ) -> CashForecastResponse:
        return await self.cash_forecast.calculate(organization_id, as_of, horizon_end)

    async def list_exceptions(
        self, organization_id: str, as_of: date
    ) -> list[BankingControlException]:
        return list(
            await self.session.scalars(
                select(BankingControlException)
                .where(
                    BankingControlException.organization_id == organization_id,
                    BankingControlException.status != "RECONCILED",
                )
                .order_by(BankingControlException.last_seen_at.desc())
            )
        )

    async def upsert_config(
        self,
        organization_id: str,
        actor_user_id: str,
        data: LiquidityAlertConfigurationCreate,
    ) -> LiquidityAlertConfiguration:
        if (
            data.effective_from
            and data.effective_to
            and data.effective_to < data.effective_from
        ):
            raise HTTPException(
                status_code=422,
                detail="effective_to must be on or after effective_from",
            )
        existing = await self.session.scalar(
            select(LiquidityAlertConfiguration)
            .where(
                LiquidityAlertConfiguration.organization_id == organization_id,
                LiquidityAlertConfiguration.alert_code == data.alert_code,
            )
            .with_for_update()
        )
        previous = None
        if existing is None:
            existing = LiquidityAlertConfiguration(
                organization_id=organization_id,
                created_by_user_id=actor_user_id,
            )
            self.session.add(existing)
        else:
            previous = {
                "enabled": existing.enabled,
                "threshold_amount": str(existing.threshold_amount)
                if existing.threshold_amount is not None
                else None,
            }
        existing.alert_code = data.alert_code
        existing.enabled = data.enabled
        existing.threshold_amount = data.threshold_amount
        existing.effective_from = data.effective_from
        existing.effective_to = data.effective_to
        existing.currency = data.currency
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="LIQUIDITY_ALERT_CONFIGURATION_UPSERTED",
            resource_type="LiquidityAlertConfiguration",
            resource_id=existing.id,
            previous_value=previous,
            new_value=data.model_dump(mode="json"),
        )
        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def _customer_unapplied(
        self, organization_id: str, as_of: date
    ) -> Decimal | None:
        payments = list(
            await self.session.scalars(
                select(Payment).where(
                    Payment.organization_id == organization_id,
                    Payment.payment_date <= as_of,
                )
            )
        )
        if not payments:
            return ZERO
        result = ZERO
        for payment in payments:
            explicit = await self.session.scalar(
                select(
                    func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0)
                ).where(
                    PaymentAllocation.organization_id == organization_id,
                    PaymentAllocation.payment_id == payment.id,
                )
            )
            explicit_amount = Decimal(explicit or ZERO)
            allocated = explicit_amount
            result += max(ZERO, Decimal(payment.amount) - allocated)
        return result.quantize(CENT)

    async def _supplier_unapplied(
        self, organization_id: str, as_of: date
    ) -> Decimal | None:
        payments = list(
            await self.session.scalars(
                select(SupplierPayment).where(
                    SupplierPayment.organization_id == organization_id,
                    SupplierPayment.payment_date <= as_of,
                )
            )
        )
        if not payments:
            return ZERO
        result = ZERO
        for payment in payments:
            explicit = await self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(SupplierPaymentAllocation.allocated_amount), 0
                    )
                ).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.supplier_payment_id == payment.id,
                )
            )
            explicit_amount = Decimal(explicit or ZERO)
            allocated = explicit_amount
            result += max(ZERO, Decimal(payment.amount) - allocated)
        return result.quantize(CENT)

    async def _current_cash(self, organization_id: str, as_of: date) -> Decimal | None:
        accounts = list(
            await self.session.scalars(
                select(TreasuryBankAccount).where(
                    TreasuryBankAccount.organization_id == organization_id,
                    TreasuryBankAccount.is_active.is_(True),
                )
            )
        )
        if not accounts:
            return None
        account_ids = {account.ledger_account_id for account in accounts}
        movements = list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.bank_account_id.in_(account_ids),
                    BankTransaction.transaction_date <= as_of,
                )
            )
        )
        opening = sum((Decimal(account.opening_balance) for account in accounts), ZERO)
        movement = sum((Decimal(item.amount) for item in movements), ZERO)
        return (opening + movement).quantize(CENT)

    async def _unresolved_exposure(self, organization_id: str, as_of: date) -> Decimal:
        rows = list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.transaction_date <= as_of,
                )
            )
        )
        ids = [row.id for row in rows]
        if not ids:
            return ZERO
        unresolved = list(
            await self.session.scalars(
                select(BankingControlException).where(
                    BankingControlException.organization_id == organization_id,
                    BankingControlException.bank_transaction_id.in_(ids),
                    BankingControlException.status != "RECONCILED",
                )
            )
        )
        amounts = {row.id: Decimal(row.amount).copy_abs() for row in rows}
        return sum(
            (amounts.get(item.bank_transaction_id, ZERO) for item in unresolved), ZERO
        ).quantize(CENT)

    async def _active_configs(
        self, organization_id: str, as_of: date
    ) -> dict[str, LiquidityAlertConfiguration]:
        configs = list(
            await self.session.scalars(
                select(LiquidityAlertConfiguration).where(
                    LiquidityAlertConfiguration.organization_id == organization_id,
                    LiquidityAlertConfiguration.enabled.is_(True),
                    (
                        LiquidityAlertConfiguration.effective_from.is_(None)
                        | (LiquidityAlertConfiguration.effective_from <= as_of)
                    ),
                    (
                        LiquidityAlertConfiguration.effective_to.is_(None)
                        | (LiquidityAlertConfiguration.effective_to >= as_of)
                    ),
                )
            )
        )
        return {item.alert_code: item for item in configs}

    @staticmethod
    def _threshold(
        configs: dict[str, LiquidityAlertConfiguration], code: str
    ) -> Decimal | None:
        item = configs.get(code)
        return (
            Decimal(item.threshold_amount).quantize(CENT)
            if item and item.threshold_amount is not None
            else None
        )

    def _alerts(
        self,
        *,
        as_of: date,
        horizon_end: date,
        current_cash: Decimal | None,
        forecast: CashForecastResponse,
        cross: BankingCrossReconciliationResponse,
        liquidity_gap: Decimal | None,
        configs: dict[str, LiquidityAlertConfiguration],
    ) -> list[LiquidityAlert]:
        alerts: list[LiquidityAlert] = []
        low_threshold = self._threshold(configs, "LOW_LIQUIDITY")
        if low_threshold is None:
            alerts.append(
                self._not_ready(
                    "LOW_LIQUIDITY",
                    as_of,
                    horizon_end,
                    "No LOW_LIQUIDITY threshold is configured",
                )
            )
        elif current_cash is not None and current_cash < low_threshold:
            alerts.append(
                LiquidityAlert(
                    code="LOW_LIQUIDITY",
                    severity="HIGH",
                    status="TRIGGERED",
                    explanation="Current cash is below the configured threshold",
                    source_data=[
                        "TreasuryBankAccount",
                        "BankTransaction",
                        "LiquidityAlertConfiguration",
                    ],
                    as_of=as_of,
                    horizon_end=horizon_end,
                    affected_amount=current_cash,
                )
            )
        if forecast.status != "READY":
            alerts.append(
                self._not_ready(
                    "CASH_FORECAST_NOT_READY",
                    as_of,
                    horizon_end,
                    "Cash Forecast is incomplete or not ready",
                )
            )
        elif forecast.projected_closing_cash < ZERO:
            alerts.append(
                LiquidityAlert(
                    code="NEGATIVE_FORECAST",
                    severity="CRITICAL",
                    status="TRIGGERED",
                    explanation="Projected closing cash is negative",
                    source_data=["CashForecastService"],
                    as_of=as_of,
                    horizon_end=horizon_end,
                    affected_amount=forecast.projected_closing_cash,
                )
            )
        if cross.unresolved_transactions:
            alerts.append(
                LiquidityAlert(
                    code="UNRESOLVED_BANK_TRANSACTIONS",
                    severity="HIGH",
                    status="TRIGGERED",
                    explanation="Imported bank transactions remain unresolved",
                    source_data=["BankingCrossReconciliationService"],
                    as_of=as_of,
                    horizon_end=horizon_end,
                    affected_amount=cross.unresolved_transactions,
                )
            )
        if liquidity_gap is None:
            alerts.append(
                self._not_ready(
                    "LIQUIDITY_GAP",
                    as_of,
                    horizon_end,
                    "No liquidity threshold is configured",
                )
            )
        elif liquidity_gap < ZERO:
            alerts.append(
                LiquidityAlert(
                    code="LIQUIDITY_GAP",
                    severity="HIGH",
                    status="TRIGGERED",
                    explanation="Forecast cash is below the configured required liquidity threshold",
                    source_data=["CashForecastService", "LiquidityAlertConfiguration"],
                    as_of=as_of,
                    horizon_end=horizon_end,
                    affected_amount=liquidity_gap.copy_abs(),
                )
            )
        return alerts

    @staticmethod
    def _not_ready(
        code: str, as_of: date, horizon_end: date, explanation: str
    ) -> LiquidityAlert:
        return LiquidityAlert(
            code=code,
            severity="INFO",
            status="NOT_READY",
            explanation=explanation,
            source_data=["LiquidityAlertConfiguration"],
            as_of=as_of,
            horizon_end=horizon_end,
        )
