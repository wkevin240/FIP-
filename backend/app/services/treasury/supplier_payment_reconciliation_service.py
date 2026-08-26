from datetime import date
from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.journal_entry import JournalEntry
from app.models.procurement import SupplierPayment, SupplierPaymentAccountingPosting
from app.models.supplier_payment_allocation import SupplierPaymentAllocation
from app.schemas.treasury.supplier_payment_reconciliation import (
    SupplierPaymentReconciliationCandidate,
    SupplierPaymentReconciliationPreview,
)
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class SupplierPaymentReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def preview(
        self,
        organization_id: str,
        bank_transaction_id: str,
        date_window_days: int = 5,
    ) -> SupplierPaymentReconciliationPreview:
        if date_window_days < 0 or date_window_days > 90:
            raise HTTPException(
                status_code=422, detail="date_window_days must be between 0 and 90"
            )
        transaction = await self.session.scalar(
            select(BankTransaction).where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.id == bank_transaction_id,
            )
        )
        if transaction is None:
            raise HTTPException(status_code=404, detail="Bank transaction not found")
        if transaction.reconciled_at is not None:
            return SupplierPaymentReconciliationPreview(
                organization_id=organization_id,
                bank_transaction_id=transaction.id,
                bank_amount=Decimal(transaction.amount),
                transaction_date=transaction.transaction_date,
                status="ALREADY_RECONCILED",
                candidates=[],
            )
        if Decimal(transaction.amount) >= 0:
            return SupplierPaymentReconciliationPreview(
                organization_id=organization_id,
                bank_transaction_id=transaction.id,
                bank_amount=Decimal(transaction.amount),
                transaction_date=transaction.transaction_date,
                status="NOT_READY",
                candidates=[],
            )

        bank_amount = abs(Decimal(transaction.amount))
        lower = date.fromordinal(
            transaction.transaction_date.toordinal() - date_window_days
        )
        upper = date.fromordinal(
            transaction.transaction_date.toordinal() + date_window_days
        )
        query = (
            select(SupplierPayment, SupplierPaymentAccountingPosting, JournalEntry)
            .join(
                SupplierPaymentAccountingPosting,
                and_(
                    SupplierPaymentAccountingPosting.organization_id == organization_id,
                    SupplierPaymentAccountingPosting.source_id == SupplierPayment.id,
                ),
            )
            .join(
                JournalEntry,
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.id
                    == SupplierPaymentAccountingPosting.journal_entry_id,
                ),
            )
            .where(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.payment_date.between(lower, upper),
                SupplierPaymentAccountingPosting.status == "POSTED",
                JournalEntry.status == JournalEntryStatus.POSTED,
                or_(
                    SupplierPayment.amount == bank_amount,
                    SupplierPayment.external_reference == transaction.external_id,
                    SupplierPayment.external_reference == transaction.reference,
                ),
            )
            .order_by(SupplierPayment.payment_date, SupplierPayment.external_reference)
        )
        rows = (await self.session.execute(query)).all()
        candidates: list[SupplierPaymentReconciliationCandidate] = []
        for payment, _posting, entry in rows:
            payment_amount = Decimal(payment.amount).quantize(CENT)
            allocation_summary = await self.session.execute(
                select(
                    func.sum(SupplierPaymentAllocation.amount),
                    func.count(SupplierPaymentAllocation.id),
                ).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.payment_id == payment.id,
                )
            )
            allocated_raw, allocation_count_raw = allocation_summary.one()
            allocation_count = int(allocation_count_raw or 0)
            allocated_amount = (
                None if allocation_count == 0 else Decimal(allocated_raw).quantize(CENT)
            )
            unapplied_amount = (
                None
                if allocated_amount is None
                else (payment_amount - allocated_amount).quantize(CENT)
            )
            amount_difference = (
                None
                if allocated_amount is None
                else abs(bank_amount - allocated_amount).quantize(CENT)
            )
            date_difference = abs(
                (transaction.transaction_date - payment.payment_date).days
            )
            reasons: list[str] = []
            if abs(bank_amount - payment_amount).quantize(CENT) == 0:
                reasons.append("EXACT_PAYMENT_AMOUNT")
            if amount_difference == 0:
                reasons.append("EXACT_ALLOCATED_AMOUNT")
            if payment.external_reference in {
                transaction.external_id,
                transaction.reference,
            }:
                reasons.append("REFERENCE_MATCH")
            if date_difference == 0:
                reasons.append("EXACT_DATE")
            elif date_difference <= date_window_days:
                reasons.append("DATE_WITHIN_WINDOW")
            if allocated_amount is None:
                candidate_status = "INCOMPLETE"
                reasons.append("ALLOCATIONS_ABSENT")
            elif unapplied_amount != 0:
                candidate_status = "INCOMPLETE"
                reasons.append("PAYMENT_PARTIALLY_ALLOCATED")
            elif amount_difference != 0:
                candidate_status = "INCOMPLETE"
                reasons.append("BANK_ALLOCATION_AMOUNT_MISMATCH")
            else:
                candidate_status = "READY"
                reasons.append("ALLOCATIONS_COMPLETE")
            candidates.append(
                SupplierPaymentReconciliationCandidate(
                    payment_id=payment.id,
                    external_reference=payment.external_reference,
                    payment_date=payment.payment_date,
                    payment_amount=payment_amount,
                    bank_transaction_id=transaction.id,
                    bank_amount=Decimal(transaction.amount),
                    amount_difference=amount_difference,
                    allocated_amount=allocated_amount,
                    unapplied_amount=unapplied_amount,
                    allocation_count=allocation_count,
                    date_difference_days=date_difference,
                    journal_entry_id=entry.id,
                    status=candidate_status,
                    match_reasons=reasons,
                )
            )
        if not candidates:
            status = "NOT_READY"
        elif any(candidate.status == "READY" for candidate in candidates):
            status = "READY"
        else:
            status = "INCOMPLETE"
        return SupplierPaymentReconciliationPreview(
            organization_id=organization_id,
            bank_transaction_id=transaction.id,
            bank_amount=Decimal(transaction.amount),
            transaction_date=transaction.transaction_date,
            status=status,
            candidates=candidates,
        )
