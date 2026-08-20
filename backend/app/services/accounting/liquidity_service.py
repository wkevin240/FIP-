from datetime import date
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.invoicing.invoice import Invoice
from app.models.procurement import PurchaseInvoice
from app.models.treasury.bank_account import TreasuryBankAccount
from app.schemas.accounting.liquidity import (
    LiquidityAccountPosition,
    LiquidityPositionResponse,
)
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class LiquidityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def validate_dates(period_start: date, as_of_date: date) -> None:
        if period_start > as_of_date:
            raise HTTPException(
                status_code=422, detail="period_start must not exceed as_of_date"
            )

    async def calculate(
        self,
        organization_id: str,
        period_start: date,
        as_of_date: date,
    ) -> LiquidityPositionResponse:
        self.validate_dates(period_start, as_of_date)
        accounts = list(
            await self.session.scalars(
                select(TreasuryBankAccount)
                .where(
                    TreasuryBankAccount.organization_id == organization_id,
                    TreasuryBankAccount.is_active.is_(True),
                )
                .order_by(TreasuryBankAccount.account_name, TreasuryBankAccount.id)
            )
        )
        blockers: list[str] = []
        positions: list[LiquidityAccountPosition] = []
        for account in accounts:
            rows = list(
                await self.session.scalars(
                    select(BankTransaction)
                    .where(
                        BankTransaction.organization_id == organization_id,
                        BankTransaction.bank_account_id == account.ledger_account_id,
                        BankTransaction.transaction_date.between(
                            period_start, as_of_date
                        ),
                    )
                    .order_by(BankTransaction.transaction_date, BankTransaction.id)
                )
            )
            movement = sum((Decimal(row.amount) for row in rows), Decimal("0.00"))
            inflows = sum(
                (Decimal(row.amount) for row in rows if Decimal(row.amount) > 0),
                Decimal("0.00"),
            )
            outflows = sum(
                (abs(Decimal(row.amount)) for row in rows if Decimal(row.amount) < 0),
                Decimal("0.00"),
            )
            opening = Decimal(account.opening_balance)
            positions.append(
                LiquidityAccountPosition(
                    treasury_bank_account_id=account.id,
                    account_name=account.account_name,
                    currency=account.currency,
                    opening_balance=opening,
                    movement_total=movement.quantize(CENT),
                    closing_balance=(opening + movement).quantize(CENT),
                    inflows=inflows.quantize(CENT),
                    outflows=outflows.quantize(CENT),
                    transaction_count=len(rows),
                )
            )
        if not accounts:
            blockers.append("NO_ACTIVE_TREASURY_BANK_ACCOUNT")
        available_cash = sum(
            (position.closing_balance for position in positions), Decimal("0.00")
        ).quantize(CENT)
        receivables = await self.session.scalar(
            select(
                func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0)
            ).where(
                Invoice.organization_id == organization_id,
                Invoice.status.not_in(["CANCELLED"]),
            )
        )
        payables = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        PurchaseInvoice.total_amount - PurchaseInvoice.paid_amount
                    ),
                    0,
                )
            ).where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.status.not_in(["CANCELLED"]),
            )
        )
        receivables_amount = Decimal(receivables or 0).quantize(CENT)
        payables_amount = Decimal(payables or 0).quantize(CENT)
        blockers.append("CASH_FORECAST_MAPPING_NOT_CONFIGURED")
        status = "READY" if accounts else "NOT_READY"
        return LiquidityPositionResponse(
            organization_id=organization_id,
            period_start=period_start,
            as_of_date=as_of_date,
            status=status,
            available_cash=available_cash,
            receivables_outstanding=receivables_amount,
            payables_outstanding=payables_amount,
            net_liquidity=(
                available_cash + receivables_amount - payables_amount
            ).quantize(CENT),
            forecast_cash_status="NOT_READY",
            bank_accounts=positions,
            blockers=blockers,
        )
