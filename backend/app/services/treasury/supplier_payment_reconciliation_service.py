from datetime import date
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.journal_entry import JournalEntry
from app.models.procurement import SupplierPayment, SupplierPaymentAccountingPosting
from app.schemas.treasury.supplier_payment_reconciliation import (
    SupplierPaymentReconciliationCandidate,
    SupplierPaymentReconciliationPreview,
)
from fastapi import HTTPException
from sqlalchemy import and_, or_, select
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
            payment_amount = Decimal(payment.amount)
            amount_difference = abs(bank_amount - payment_amount).quantize(CENT)
            date_difference = abs(
                (transaction.transaction_date - payment.payment_date).days
            )
            reasons: list[str] = []
            if amount_difference == 0:
                reasons.append("EXACT_AMOUNT")
            if payment.external_reference in {
                transaction.external_id,
                transaction.reference,
            }:
                reasons.append("REFERENCE_MATCH")
            if date_difference == 0:
                reasons.append("EXACT_DATE")
            elif date_difference <= date_window_days:
                reasons.append("DATE_WITHIN_WINDOW")
            candidates.append(
                SupplierPaymentReconciliationCandidate(
                    payment_id=payment.id,
                    external_reference=payment.external_reference,
                    payment_date=payment.payment_date,
                    payment_amount=payment_amount,
                    bank_transaction_id=transaction.id,
                    bank_amount=Decimal(transaction.amount),
                    amount_difference=amount_difference,
                    date_difference_days=date_difference,
                    journal_entry_id=entry.id,
                    status="PROPOSED",
                    match_reasons=reasons,
                )
            )
        return SupplierPaymentReconciliationPreview(
            organization_id=organization_id,
            bank_transaction_id=transaction.id,
            bank_amount=Decimal(transaction.amount),
            transaction_date=transaction.transaction_date,
            status="CANDIDATES_FOUND" if candidates else "NO_MATCH",
            candidates=candidates,
        )
