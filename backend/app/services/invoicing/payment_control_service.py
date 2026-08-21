from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from app.models.invoicing.invoice import Invoice
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import (
    PaymentAllocation,
    SupplierPaymentAllocation,
)
from app.models.procurement import PurchaseInvoice, SupplierPayment
from app.schemas.invoicing.payment_control import (
    PaymentAllocationCreate,
    PaymentControlResponse,
    PaymentReconciliationResponse,
    SupplierPaymentAllocationCreate,
    SupplierPaymentControlResponse,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class PaymentControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def allocate_customer(
        self, organization_id: str, actor_user_id: str, data: PaymentAllocationCreate
    ) -> PaymentAllocation:
        existing = await self.session.scalar(
            select(PaymentAllocation).where(
                PaymentAllocation.organization_id == organization_id,
                PaymentAllocation.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            return existing
        payment = await self.session.scalar(
            select(Payment)
            .where(
                Payment.organization_id == organization_id,
                Payment.id == data.payment_id,
            )
            .with_for_update()
        )
        invoice = await self.session.scalar(
            select(Invoice)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.id == data.invoice_id,
            )
            .with_for_update()
        )
        if payment is None or invoice is None:
            raise HTTPException(status_code=404, detail="Payment or invoice not found")
        allocated = await self._customer_allocated(organization_id, payment.id)
        if allocated + data.allocated_amount > Decimal(payment.amount):
            raise HTTPException(
                status_code=422, detail="Payment allocation exceeds payment amount"
            )
        invoice_allocated = await self.session.scalar(
            select(
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0)
            ).where(
                PaymentAllocation.organization_id == organization_id,
                PaymentAllocation.invoice_id == invoice.id,
            )
        )
        remaining = (
            Decimal(invoice.total_amount)
            - Decimal(invoice.credited_amount)
            - Decimal(invoice.paid_amount)
            - Decimal(invoice_allocated or ZERO)
        )
        if data.allocated_amount > remaining:
            raise HTTPException(
                status_code=422,
                detail="Payment allocation exceeds invoice remaining amount",
            )
        row = PaymentAllocation(organization_id=organization_id, **data.model_dump())
        self.session.add(row)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="CUSTOMER_PAYMENT_ALLOCATED",
            resource_type="PaymentAllocation",
            resource_id=row.id,
            new_value={
                "payment_id": payment.id,
                "invoice_id": invoice.id,
                "allocated_amount": str(data.allocated_amount),
            },
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment allocation already exists or changed concurrently",
            ) from exc
        await self.session.refresh(row)
        return row

    async def allocate_supplier(
        self,
        organization_id: str,
        actor_user_id: str,
        data: SupplierPaymentAllocationCreate,
    ) -> SupplierPaymentAllocation:
        existing = await self.session.scalar(
            select(SupplierPaymentAllocation).where(
                SupplierPaymentAllocation.organization_id == organization_id,
                SupplierPaymentAllocation.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            return existing
        payment = await self.session.scalar(
            select(SupplierPayment)
            .where(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.id == data.supplier_payment_id,
            )
            .with_for_update()
        )
        invoice = await self.session.scalar(
            select(PurchaseInvoice)
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.id == data.purchase_invoice_id,
            )
            .with_for_update()
        )
        if payment is None or invoice is None:
            raise HTTPException(
                status_code=404, detail="Supplier payment or invoice not found"
            )
        allocated = await self._supplier_allocated(organization_id, payment.id)
        if allocated + data.allocated_amount > Decimal(payment.amount):
            raise HTTPException(
                status_code=422,
                detail="Supplier payment allocation exceeds payment amount",
            )
        invoice_allocated = await self.session.scalar(
            select(
                func.coalesce(func.sum(SupplierPaymentAllocation.allocated_amount), 0)
            ).where(
                SupplierPaymentAllocation.organization_id == organization_id,
                SupplierPaymentAllocation.purchase_invoice_id == invoice.id,
            )
        )
        remaining = (
            Decimal(invoice.total_amount)
            - Decimal(invoice.paid_amount)
            - Decimal(invoice_allocated or ZERO)
        )
        if data.allocated_amount > remaining:
            raise HTTPException(
                status_code=422,
                detail="Supplier payment allocation exceeds invoice remaining amount",
            )
        row = SupplierPaymentAllocation(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(row)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SUPPLIER_PAYMENT_ALLOCATED",
            resource_type="SupplierPaymentAllocation",
            resource_id=row.id,
            new_value={
                "supplier_payment_id": payment.id,
                "purchase_invoice_id": invoice.id,
                "allocated_amount": str(data.allocated_amount),
            },
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier payment allocation already exists or changed concurrently",
            ) from exc
        await self.session.refresh(row)
        return row

    async def customer_control(
        self, organization_id: str, payment_id: str
    ) -> PaymentControlResponse:
        payment = await self.session.scalar(
            select(Payment).where(
                Payment.organization_id == organization_id, Payment.id == payment_id
            )
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        rows = list(
            await self.session.scalars(
                select(PaymentAllocation)
                .where(
                    PaymentAllocation.organization_id == organization_id,
                    PaymentAllocation.payment_id == payment_id,
                )
                .order_by(PaymentAllocation.created_at, PaymentAllocation.id)
            )
        )
        allocated = sum((Decimal(row.allocated_amount) for row in rows), ZERO)
        if not rows:
            allocated = ZERO
        unapplied = max(ZERO, Decimal(payment.amount) - allocated).quantize(CENT)
        return PaymentControlResponse(
            organization_id=organization_id,
            payment_id=payment.id,
            payment_amount=Decimal(payment.amount).quantize(CENT),
            allocated_amount=allocated.quantize(CENT),
            unapplied_amount=unapplied,
            status="FULLY_APPLIED"
            if unapplied == ZERO
            else "PARTIALLY_APPLIED"
            if allocated > ZERO
            else "UNAPPLIED",
            allocations=rows,
            blockers=[],
        )

    async def supplier_control(
        self, organization_id: str, payment_id: str
    ) -> SupplierPaymentControlResponse:
        payment = await self.session.scalar(
            select(SupplierPayment).where(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.id == payment_id,
            )
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Supplier payment not found")
        rows = list(
            await self.session.scalars(
                select(SupplierPaymentAllocation)
                .where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.supplier_payment_id == payment_id,
                )
                .order_by(
                    SupplierPaymentAllocation.created_at, SupplierPaymentAllocation.id
                )
            )
        )
        allocated = sum((Decimal(row.allocated_amount) for row in rows), ZERO)
        if not rows:
            allocated = ZERO
        unapplied = max(ZERO, Decimal(payment.amount) - allocated).quantize(CENT)
        return SupplierPaymentControlResponse(
            organization_id=organization_id,
            supplier_payment_id=payment.id,
            payment_amount=Decimal(payment.amount).quantize(CENT),
            allocated_amount=allocated.quantize(CENT),
            unapplied_amount=unapplied,
            status="FULLY_APPLIED"
            if unapplied == ZERO
            else "PARTIALLY_APPLIED"
            if allocated > ZERO
            else "UNAPPLIED",
            allocations=rows,
            blockers=[],
        )

    async def _customer_allocated(
        self, organization_id: str, payment_id: str
    ) -> Decimal:
        value = await self.session.scalar(
            select(
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0)
            ).where(
                PaymentAllocation.organization_id == organization_id,
                PaymentAllocation.payment_id == payment_id,
            )
        )
        return Decimal(value or ZERO)

    async def _supplier_allocated(
        self, organization_id: str, payment_id: str
    ) -> Decimal:
        value = await self.session.scalar(
            select(
                func.coalesce(func.sum(SupplierPaymentAllocation.allocated_amount), 0)
            ).where(
                SupplierPaymentAllocation.organization_id == organization_id,
                SupplierPaymentAllocation.supplier_payment_id == payment_id,
            )
        )
        return Decimal(value or ZERO)

    async def reconciliation(
        self, organization_id: str, as_of
    ) -> PaymentReconciliationResponse:
        customer = list(
            await self.session.scalars(
                select(Payment).where(
                    Payment.organization_id == organization_id,
                    Payment.payment_date <= as_of,
                )
            )
        )
        supplier = list(
            await self.session.scalars(
                select(SupplierPayment).where(
                    SupplierPayment.organization_id == organization_id,
                    SupplierPayment.payment_date <= as_of,
                )
            )
        )
        bank_transactions = list(
            await self.session.scalars(
                select(BankTransaction).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.transaction_date <= as_of,
                )
            )
        )
        customer_unapplied = ZERO
        for payment in customer:
            control = await self.customer_control(organization_id, payment.id)
            customer_unapplied += control.unapplied_amount
        supplier_unapplied = ZERO
        for payment in supplier:
            control = await self.supplier_control(organization_id, payment.id)
            supplier_unapplied += control.unapplied_amount

        payment_without_bank = 0
        amount_differences = ZERO
        ambiguous_matches = 0
        matched_bank_ids: set[str] = set()
        for payment, expected_amount in [
            *((item, Decimal(item.amount)) for item in customer),
            *((item, -Decimal(item.amount)) for item in supplier),
        ]:
            reference = getattr(payment, "external_reference", None)
            if not reference:
                payment_without_bank += 1
                continue
            reference = reference.strip()
            candidates = [
                transaction
                for transaction in bank_transactions
                if transaction.id not in matched_bank_ids
                and transaction.transaction_date == payment.payment_date
                and reference
                in {
                    (transaction.external_id or "").strip(),
                    (transaction.reference or "").strip(),
                }
            ]
            if len(candidates) == 0:
                payment_without_bank += 1
                continue
            if len(candidates) > 1:
                ambiguous_matches += 1
                payment_without_bank += 1
                continue
            transaction = candidates[0]
            matched_bank_ids.add(transaction.id)
            amount_differences += abs(expected_amount - Decimal(transaction.amount))

        bank_without_payment = len(
            [
                transaction
                for transaction in bank_transactions
                if transaction.id not in matched_bank_ids
            ]
        )
        blockers: list[str] = []
        if not customer and not supplier:
            blockers.append("NO_PAYMENT_SOURCE")
        if not bank_transactions:
            blockers.append("NO_BANK_TRANSACTION_SOURCE")
        if customer or supplier:
            if not bank_transactions:
                blockers.append("PAYMENT_BANK_RELATION_NOT_READY")
            elif payment_without_bank:
                blockers.append("UNMATCHED_PAYMENTS")
        if bank_transactions and not (customer or supplier):
            blockers.append("BANK_PAYMENT_RELATION_NOT_READY")
        if bank_without_payment:
            blockers.append("UNMATCHED_BANK_TRANSACTIONS")
        if ambiguous_matches:
            blockers.append("AMBIGUOUS_PAYMENT_BANK_MATCH")
        amount_differences = amount_differences.quantize(CENT)
        if amount_differences:
            blockers.append("PAYMENT_BANK_AMOUNT_DIFFERENCE")
        blockers = list(dict.fromkeys(blockers))
        if not customer and not supplier or not bank_transactions:
            reconciliation_status = "NOT_READY"
        elif blockers:
            reconciliation_status = "INCOMPLETE"
        else:
            reconciliation_status = "READY"
        return PaymentReconciliationResponse(
            organization_id=organization_id,
            as_of=as_of,
            status=reconciliation_status,
            customer_unapplied_payments=customer_unapplied.quantize(CENT),
            supplier_unapplied_payments=supplier_unapplied.quantize(CENT),
            payment_without_bank_transaction=payment_without_bank,
            bank_transaction_without_payment=bank_without_payment,
            amount_differences=amount_differences,
            blockers=blockers,
        )
