from datetime import date
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.invoicing.invoice import Invoice
from app.models.procurement import PurchaseInvoice
from app.models.treasury.banking_control import BankingControlException
from app.schemas.treasury.banking_cross_reconciliation import (
    BankingCrossReconciliationResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BankingCrossReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report(
        self, organization_id: str, as_of: date
    ) -> BankingCrossReconciliationResponse:
        transactions = list(
            (
                await self.session.scalars(
                    select(BankTransaction).where(
                        BankTransaction.organization_id == organization_id,
                        BankTransaction.transaction_date <= as_of,
                    )
                )
            ).all()
        )
        controls = list(
            (
                await self.session.scalars(
                    select(BankingControlException).where(
                        BankingControlException.organization_id == organization_id,
                        BankingControlException.bank_transaction_id.in_(
                            [transaction.id for transaction in transactions]
                        )
                        if transactions
                        else False,
                    )
                )
            ).all()
        )
        by_transaction = {
            control.bank_transaction_id: control.status for control in controls
        }
        status_counts: dict[str, int] = {}
        inflows = Decimal("0.00")
        outflows = Decimal("0.00")
        for transaction in transactions:
            amount = Decimal(transaction.amount).quantize(Decimal("0.01"))
            if amount >= Decimal("0.00"):
                inflows += amount
            else:
                outflows += abs(amount)
            control_status = by_transaction.get(transaction.id, "PENDING")
            status_counts[control_status] = status_counts.get(control_status, 0) + 1
        reconciled = status_counts.get("RECONCILED", 0)
        unresolved = len(transactions) - reconciled

        ar_invoices = list(
            (
                await self.session.scalars(
                    select(Invoice).where(
                        Invoice.organization_id == organization_id,
                        Invoice.status.in_(["ISSUED", "PARTIALLY_PAID"]),
                        Invoice.invoice_date <= as_of,
                    )
                )
            ).all()
        )
        ap_invoices = list(
            (
                await self.session.scalars(
                    select(PurchaseInvoice).where(
                        PurchaseInvoice.organization_id == organization_id,
                        PurchaseInvoice.status.in_(["VALIDATED", "PARTIALLY_PAID"]),
                        PurchaseInvoice.invoice_date <= as_of,
                    )
                )
            ).all()
        )
        ar_outstanding = sum(
            (invoice.outstanding_amount for invoice in ar_invoices), Decimal("0.00")
        )
        ap_outstanding = sum(
            (invoice.outstanding_amount for invoice in ap_invoices), Decimal("0.00")
        )
        blockers: list[str] = []
        if not transactions:
            blockers.append("NO_BANK_TRANSACTIONS")
        if transactions and unresolved:
            blockers.append("UNRESOLVED_BANK_TRANSACTIONS")
        if not ar_invoices:
            blockers.append("NO_OPEN_AR_SOURCE")
        if not ap_invoices:
            blockers.append("NO_OPEN_AP_SOURCE")
        status = "READY" if transactions and unresolved == 0 else "INCOMPLETE"
        return BankingCrossReconciliationResponse(
            organization_id=organization_id,
            as_of=as_of,
            status=status,
            imported_transactions=len(transactions),
            reconciled_transactions=reconciled,
            unresolved_transactions=unresolved,
            bank_inflows=inflows.quantize(Decimal("0.01")),
            bank_outflows=outflows.quantize(Decimal("0.01")),
            net_bank_movement=(inflows - outflows).quantize(Decimal("0.01")),
            ar_outstanding=ar_outstanding.quantize(Decimal("0.01")),
            ap_outstanding=ap_outstanding.quantize(Decimal("0.01")),
            status_counts=status_counts,
            blockers=blockers,
        )
