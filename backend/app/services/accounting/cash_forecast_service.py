from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.invoicing.invoice import Invoice
from app.models.procurement import PurchaseInvoice
from app.models.treasury.bank_account import TreasuryBankAccount
from app.schemas.accounting.cash_forecast import (
    CashForecastLine,
    CashForecastResponse,
)
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class CashForecastService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def validate_dates(period_start: date, period_end: date) -> None:
        if period_start > period_end:
            raise HTTPException(
                status_code=422, detail="period_start must not exceed period_end"
            )

    async def calculate(
        self,
        organization_id: str,
        period_start: date,
        period_end: date,
    ) -> CashForecastResponse:
        self.validate_dates(period_start, period_end)
        accounts = list(
            await self.session.scalars(
                select(TreasuryBankAccount).where(
                    TreasuryBankAccount.organization_id == organization_id,
                    TreasuryBankAccount.is_active.is_(True),
                )
            )
        )
        blockers: list[str] = []
        if not accounts:
            blockers.append("NO_ACTIVE_TREASURY_BANK_ACCOUNT")

        movements = list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.transaction_date <= period_end,
                )
            )
        )
        account_ids = {account.ledger_account_id for account in accounts}
        movements = [
            movement
            for movement in movements
            if movement.bank_account_id in account_ids
        ]
        opening_cash = sum(
            (Decimal(account.opening_balance) for account in accounts), ZERO
        ) + sum(
            (
                Decimal(movement.amount)
                for movement in movements
                if movement.transaction_date < period_start
            ),
            ZERO,
        )
        actual_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
        for movement in movements:
            if period_start <= movement.transaction_date <= period_end:
                actual_by_date[movement.transaction_date] += Decimal(movement.amount)

        invoices = list(
            await self.session.scalars(
                select(Invoice).where(
                    Invoice.organization_id == organization_id,
                    Invoice.due_date.is_not(None),
                    Invoice.due_date.between(period_start, period_end),
                    Invoice.status.in_(["ISSUED", "PARTIALLY_PAID"]),
                )
            )
        )
        ar_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
        for invoice in invoices:
            outstanding = (
                Decimal(invoice.total_amount)
                - Decimal(invoice.paid_amount)
                - Decimal(invoice.credited_amount)
            )
            if outstanding > ZERO:
                ar_by_date[invoice.due_date] += outstanding

        purchase_invoices = list(
            await self.session.scalars(
                select(PurchaseInvoice).where(
                    PurchaseInvoice.organization_id == organization_id,
                    PurchaseInvoice.due_date.is_not(None),
                    PurchaseInvoice.due_date.between(period_start, period_end),
                    PurchaseInvoice.status.in_(["VALIDATED", "PARTIALLY_PAID"]),
                )
            )
        )
        ap_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
        for invoice in purchase_invoices:
            outstanding = Decimal(invoice.total_amount) - Decimal(invoice.paid_amount)
            if outstanding > ZERO:
                ap_by_date[invoice.due_date] += outstanding

        if not invoices:
            blockers.append("NO_DUE_RECEIVABLES_IN_PERIOD")
        if not purchase_invoices:
            blockers.append("NO_DUE_PAYABLES_IN_PERIOD")

        lines: list[CashForecastLine] = []
        running_cash = opening_cash
        cursor = period_start
        while cursor <= period_end:
            actual = actual_by_date[cursor]
            inflow = ar_by_date[cursor]
            outflow = ap_by_date[cursor]
            net = actual + inflow - outflow
            running_cash += net
            lines.append(
                CashForecastLine(
                    forecast_date=cursor,
                    actual_bank_movement=actual.quantize(CENT),
                    expected_ar_inflow=inflow.quantize(CENT),
                    expected_ap_outflow=outflow.quantize(CENT),
                    projected_net_movement=net.quantize(CENT),
                    projected_closing_cash=running_cash.quantize(CENT),
                )
            )
            cursor += timedelta(days=1)

        expected_inflows = sum(ar_by_date.values(), ZERO)
        expected_outflows = sum(ap_by_date.values(), ZERO)
        actual_movement = sum(actual_by_date.values(), ZERO)
        source_status = "READY" if accounts else "NOT_READY"
        status = (
            "READY"
            if accounts and (invoices or purchase_invoices or actual_by_date)
            else "NOT_READY"
        )
        return CashForecastResponse(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            status=status,
            opening_cash=opening_cash.quantize(CENT),
            actual_cash_movement=actual_movement.quantize(CENT),
            expected_ar_inflows=expected_inflows.quantize(CENT),
            expected_ap_outflows=expected_outflows.quantize(CENT),
            projected_closing_cash=running_cash.quantize(CENT),
            forecast_source_status=source_status,
            lines=lines,
            blockers=blockers,
        )
