from datetime import date
from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_reconciliation_allocation import (
    BankReconciliationAllocation,
)
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.journal_entry import JournalEntry
from app.models.invoicing.payment import Payment
from app.models.invoicing.settlement_accounting import PaymentAccountingPosting
from app.models.procurement import SupplierPayment, SupplierPaymentAccountingPosting
from app.schemas.treasury.reconciliation import (
    AccountingTreasuryReconciliationResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class AccountingTreasuryReconciliationService:
    """Read-only proof that bank, settlement and posted-ledger sources agree."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report(
        self, organization_id: str, as_of: date
    ) -> AccountingTreasuryReconciliationResponse:
        payments = list(
            await self.session.scalars(
                select(Payment).where(
                    Payment.organization_id == organization_id,
                    Payment.payment_date <= as_of,
                )
            )
        )
        supplier_payments = list(
            await self.session.scalars(
                select(SupplierPayment).where(
                    SupplierPayment.organization_id == organization_id,
                    SupplierPayment.payment_date <= as_of,
                )
            )
        )
        transactions = list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.transaction_date <= as_of,
                )
            )
        )
        payment_postings = {
            row.source_id: row
            for row in await self.session.scalars(
                select(PaymentAccountingPosting).where(
                    PaymentAccountingPosting.organization_id == organization_id,
                    PaymentAccountingPosting.status == "POSTED",
                )
            )
        }
        supplier_postings = {
            row.source_id: row
            for row in await self.session.scalars(
                select(SupplierPaymentAccountingPosting).where(
                    SupplierPaymentAccountingPosting.organization_id == organization_id,
                    SupplierPaymentAccountingPosting.status == "POSTED",
                )
            )
        }
        entries = {
            row.id: row
            for row in await self.session.scalars(
                select(JournalEntry).where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.status == JournalEntryStatus.POSTED,
                )
            )
        }
        reconciled_ids = {
            row.bank_transaction_id
            for row in await self.session.scalars(
                select(BankReconciliation).where(
                    BankReconciliation.organization_id == organization_id,
                )
            )
        }
        allocated_totals: dict[str, Decimal] = {}
        allocations = await self.session.scalars(
            select(BankReconciliationAllocation).where(
                BankReconciliationAllocation.organization_id == organization_id,
            )
        )
        for allocation in allocations:
            allocated_totals[allocation.bank_transaction_id] = allocated_totals.get(
                allocation.bank_transaction_id, ZERO
            ) + Decimal(allocation.matched_amount)

        matched_payments = 0
        unmatched_payments = 0
        ambiguous_payments = 0
        missing_postings = 0
        amount_differences = ZERO
        claimed_bank_ids: set[str] = set()
        all_payment_rows = [
            (
                payment,
                Decimal(payment.amount),
                payment.external_reference,
                payment.payment_date,
                payment_postings.get(payment.id),
            )
            for payment in payments
        ] + [
            (
                payment,
                -Decimal(payment.amount),
                payment.external_reference,
                payment.payment_date,
                supplier_postings.get(payment.id),
            )
            for payment in supplier_payments
        ]
        for (
            payment,
            expected_amount,
            reference,
            payment_date,
            posting,
        ) in all_payment_rows:
            if not reference:
                unmatched_payments += 1
                continue
            candidates = [
                transaction
                for transaction in transactions
                if transaction.id not in claimed_bank_ids
                and transaction.transaction_date == payment_date
                and reference.strip()
                in {
                    (transaction.external_id or "").strip(),
                    (transaction.reference or "").strip(),
                }
            ]
            if len(candidates) != 1:
                unmatched_payments += 1
                if len(candidates) > 1:
                    ambiguous_payments += 1
                continue
            transaction = candidates[0]
            claimed_bank_ids.add(transaction.id)
            difference = expected_amount - Decimal(transaction.amount)
            amount_differences += difference.copy_abs()
            if posting is None or posting.journal_entry_id not in entries:
                missing_postings += 1
            elif difference.quantize(CENT) == ZERO:
                matched_payments += 1

        unresolved_bank = sum(
            1
            for transaction in transactions
            if transaction.id not in reconciled_ids
            and allocated_totals.get(transaction.id, ZERO).quantize(CENT)
            != Decimal(transaction.amount).copy_abs().quantize(CENT)
        )
        blockers: list[str] = []
        if not payments and not supplier_payments:
            blockers.append("NO_PAYMENT_SOURCE")
        if not transactions:
            blockers.append("NO_BANK_TRANSACTION_SOURCE")
        if payments or supplier_payments:
            if unmatched_payments:
                blockers.append("UNMATCHED_PAYMENTS")
            if missing_postings:
                blockers.append("PAYMENT_ACCOUNTING_POSTING_NOT_READY")
        if ambiguous_payments:
            blockers.append("AMBIGUOUS_PAYMENT_BANK_MATCH")
        if amount_differences.quantize(CENT) != ZERO:
            blockers.append("PAYMENT_BANK_AMOUNT_DIFFERENCE")
        if unresolved_bank:
            blockers.append("UNRECONCILED_BANK_TRANSACTIONS")
        if not payments and not supplier_payments or not transactions:
            status = "NOT_READY"
        elif blockers:
            status = "INCOMPLETE"
        else:
            status = "READY"
        return AccountingTreasuryReconciliationResponse(
            organization_id=organization_id,
            as_of=as_of,
            status=status,
            bank_transactions=len(transactions),
            payments=len(payments) + len(supplier_payments),
            matched_payments=matched_payments,
            unmatched_payments=unmatched_payments,
            missing_postings=missing_postings,
            unresolved_bank_transactions=unresolved_bank,
            amount_differences=amount_differences.quantize(CENT),
            blockers=list(dict.fromkeys(blockers)),
        )
