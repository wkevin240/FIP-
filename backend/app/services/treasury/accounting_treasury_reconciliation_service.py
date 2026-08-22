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
from sqlalchemy import Date, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class AccountingTreasuryReconciliationService:
    """Read-only historical proof across bank, settlements and posted ledger."""

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
        candidate_entry_ids = {
            posting.journal_entry_id
            for posting in [*payment_postings.values(), *supplier_postings.values()]
        }
        entries = {
            row.id: row
            for row in await self.session.scalars(
                select(JournalEntry).where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.id.in_(candidate_entry_ids or {"__none__"}),
                    JournalEntry.status == JournalEntryStatus.POSTED,
                    JournalEntry.entry_date <= as_of,
                    (JournalEntry.posted_at.is_(None))
                    | (JournalEntry.posted_at.cast(Date) <= as_of),
                )
            )
        }
        reconciled_ids = {
            row.bank_transaction_id
            for row in await self.session.scalars(
                select(BankReconciliation).where(
                    BankReconciliation.organization_id == organization_id,
                    BankReconciliation.bank_transaction_id.in_(
                        [transaction.id for transaction in transactions] or ["__none__"]
                    ),
                )
            )
        }
        allocated_totals: dict[str, Decimal] = {}
        for allocation in await self.session.scalars(
            select(BankReconciliationAllocation).where(
                BankReconciliationAllocation.organization_id == organization_id,
                BankReconciliationAllocation.bank_transaction_id.in_(
                    [transaction.id for transaction in transactions] or ["__none__"]
                ),
            )
        ):
            allocated_totals[allocation.bank_transaction_id] = allocated_totals.get(
                allocation.bank_transaction_id, ZERO
            ) + Decimal(allocation.matched_amount)

        matched_payments = 0
        unmatched_payments = 0
        ambiguous_payments = 0
        missing_postings = 0
        missing_entries = 0
        wrong_dates = 0
        wrong_references = 0
        amount_mismatches = 0
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
            reference = (reference or "").strip()
            by_date = [
                transaction
                for transaction in transactions
                if transaction.id not in claimed_bank_ids
                and transaction.transaction_date == payment_date
            ]
            by_reference = [
                transaction
                for transaction in transactions
                if transaction.id not in claimed_bank_ids
                and reference
                and reference
                in {
                    (transaction.external_id or "").strip(),
                    (transaction.reference or "").strip(),
                }
            ]
            candidates = [
                transaction
                for transaction in by_date
                if reference
                and reference
                in {
                    (transaction.external_id or "").strip(),
                    (transaction.reference or "").strip(),
                }
            ]
            if len(candidates) > 1:
                ambiguous_payments += 1
                unmatched_payments += 1
                continue
            if not candidates:
                unmatched_payments += 1
                if not by_date:
                    wrong_dates += 1 if by_reference else 0
                elif reference and not by_reference:
                    wrong_references += 1
                continue
            transaction = candidates[0]
            claimed_bank_ids.add(transaction.id)
            difference = expected_amount - Decimal(transaction.amount)
            amount_differences += difference.copy_abs()
            if difference.quantize(CENT) != ZERO:
                amount_mismatches += 1
                continue
            if posting is None:
                missing_postings += 1
                continue
            if posting.journal_entry_id not in entries:
                missing_entries += 1
                continue
            matched_payments += 1

        unresolved_bank = 0
        residual_allocations = 0
        for transaction in transactions:
            expected = Decimal(transaction.amount).copy_abs().quantize(CENT)
            allocated = allocated_totals.get(transaction.id, ZERO).quantize(CENT)
            if transaction.id in reconciled_ids:
                continue
            if allocated < expected:
                unresolved_bank += 1
                if allocated > ZERO:
                    residual_allocations += 1

        bank_without_payment = len(
            [
                transaction
                for transaction in transactions
                if transaction.id not in claimed_bank_ids
            ]
        )
        blockers: list[str] = []
        if not payments and not supplier_payments:
            blockers.append("NO_PAYMENT_SOURCE")
        if not transactions:
            blockers.append("NO_BANK_TRANSACTION_SOURCE")
        if unmatched_payments:
            blockers.append("UNMATCHED_PAYMENTS")
        if wrong_dates:
            blockers.append("PAYMENT_BANK_WRONG_DATE")
        if wrong_references:
            blockers.append("PAYMENT_BANK_WRONG_REFERENCE")
        if ambiguous_payments:
            blockers.append("AMBIGUOUS_PAYMENT_BANK_MATCH")
        if amount_mismatches:
            blockers.append("PAYMENT_BANK_AMOUNT_DIFFERENCE")
        if missing_postings:
            blockers.append("PAYMENT_ACCOUNTING_POSTING_ABSENT")
        if missing_entries:
            blockers.append("PAYMENT_JOURNAL_ENTRY_NOT_POSTED_OR_NOT_AS_OF")
        if bank_without_payment:
            blockers.append("BANK_TRANSACTION_WITHOUT_PAYMENT")
        if unresolved_bank:
            blockers.append("UNRECONCILED_BANK_TRANSACTIONS")
        if residual_allocations:
            blockers.append("BANK_ALLOCATION_RESIDUAL")
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
            payments=len(all_payment_rows),
            matched_payments=matched_payments,
            unmatched_payments=unmatched_payments,
            missing_postings=missing_postings,
            unresolved_bank_transactions=unresolved_bank,
            amount_differences=amount_differences.quantize(CENT),
            blockers=list(dict.fromkeys(blockers)),
        )
