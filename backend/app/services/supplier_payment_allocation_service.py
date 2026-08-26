from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procurement import (
    PurchaseInvoice,
    SupplierPayment,
    SupplierPaymentAccountingPosting,
)
from app.models.supplier_payment_allocation import SupplierPaymentAllocation
from app.schemas.procurement import (
    SupplierPaymentAllocationCreate,
    SupplierPaymentReconciliationResponse,
)
from app.services.audit.audit_service import AuditService

CENT = Decimal("0.01")


class SupplierPaymentAllocationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def allocate(
        self,
        organization_id: str,
        actor_user_id: str,
        payment_id: str,
        data: SupplierPaymentAllocationCreate,
        idempotency_key: str,
    ) -> SupplierPaymentAllocation:
        key = idempotency_key.strip()
        if not key:
            raise HTTPException(
                status_code=422, detail="Idempotency-Key must not be blank"
            )
        existing = await self.session.scalar(
            select(SupplierPaymentAllocation).where(
                SupplierPaymentAllocation.organization_id == organization_id,
                SupplierPaymentAllocation.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing
        payment = await self.session.scalar(
            select(SupplierPayment)
            .where(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.id == payment_id,
            )
            .with_for_update()
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Supplier payment not found")
        posting = await self.session.scalar(
            select(SupplierPaymentAccountingPosting).where(
                SupplierPaymentAccountingPosting.organization_id == organization_id,
                SupplierPaymentAccountingPosting.source_id == payment.id,
            )
        )
        if posting is not None:
            raise HTTPException(
                status_code=409, detail="Posted supplier payment cannot be reallocated"
            )
        invoice = await self.session.scalar(
            select(PurchaseInvoice)
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.id == data.invoice_id,
            )
            .with_for_update()
        )
        if invoice is None:
            raise HTTPException(status_code=404, detail="Purchase invoice not found")
        if invoice.status not in {"VALIDATED", "PARTIALLY_PAID"}:
            raise HTTPException(
                status_code=422, detail="Purchase invoice is not payable"
            )
        if payment.payment_date < invoice.invoice_date:
            raise HTTPException(
                status_code=422, detail="Payment date precedes invoice date"
            )
        if payment.invoice_id is not None:
            source_invoice = await self.session.scalar(
                select(PurchaseInvoice.supplier_id).where(
                    PurchaseInvoice.organization_id == organization_id,
                    PurchaseInvoice.id == payment.invoice_id,
                )
            )
            if source_invoice is not None and source_invoice != invoice.supplier_id:
                raise HTTPException(status_code=422, detail="Supplier mismatch")
        allocated = Decimal(
            await self.session.scalar(
                select(
                    func.coalesce(func.sum(SupplierPaymentAllocation.amount), 0)
                ).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.payment_id == payment.id,
                )
            )
            or 0
        )
        if allocated + data.amount > Decimal(payment.amount):
            raise HTTPException(
                status_code=422, detail="Allocation exceeds payment amount"
            )
        invoice_outstanding = Decimal(invoice.total_amount) - Decimal(
            invoice.paid_amount
        )
        if data.amount > invoice_outstanding:
            raise HTTPException(
                status_code=422, detail="Allocation exceeds invoice outstanding amount"
            )
        allocation = SupplierPaymentAllocation(
            organization_id=organization_id,
            payment_id=payment.id,
            invoice_id=invoice.id,
            supplier_id=invoice.supplier_id,
            amount=data.amount,
            idempotency_key=key,
            created_by_user_id=actor_user_id,
        )
        self.session.add(allocation)
        invoice.paid_amount = (Decimal(invoice.paid_amount) + data.amount).quantize(
            CENT
        )
        invoice.status = (
            "PAID" if invoice.paid_amount == invoice.total_amount else "PARTIALLY_PAID"
        )
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SUPPLIER_PAYMENT_ALLOCATED",
            resource_type="SupplierPaymentAllocation",
            resource_id=allocation.id,
            new_value={
                "payment_id": payment.id,
                "invoice_id": invoice.id,
                "amount": str(data.amount),
            },
            request_id=key,
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(SupplierPaymentAllocation).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.idempotency_key == key,
                )
            )
            if existing is not None:
                return existing
            raise HTTPException(
                status_code=409, detail="Allocation already exists"
            ) from exc
        await self.session.refresh(allocation)
        return allocation

    async def deallocate(
        self, organization_id: str, actor_user_id: str, allocation_id: str
    ) -> None:
        allocation = await self.session.scalar(
            select(SupplierPaymentAllocation)
            .where(
                SupplierPaymentAllocation.organization_id == organization_id,
                SupplierPaymentAllocation.id == allocation_id,
            )
            .with_for_update()
        )
        if allocation is None:
            raise HTTPException(
                status_code=404, detail="Supplier payment allocation not found"
            )
        posting = await self.session.scalar(
            select(SupplierPaymentAccountingPosting).where(
                SupplierPaymentAccountingPosting.organization_id == organization_id,
                SupplierPaymentAccountingPosting.source_id == allocation.payment_id,
            )
        )
        if posting is not None:
            raise HTTPException(
                status_code=409, detail="Posted supplier payment cannot be reallocated"
            )
        invoice = await self.session.scalar(
            select(PurchaseInvoice)
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.id == allocation.invoice_id,
            )
            .with_for_update()
        )
        invoice.paid_amount = (
            Decimal(invoice.paid_amount) - Decimal(allocation.amount)
        ).quantize(CENT)
        invoice.status = "VALIDATED" if invoice.paid_amount == 0 else "PARTIALLY_PAID"
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SUPPLIER_PAYMENT_DEALLOCATED",
            resource_type="SupplierPaymentAllocation",
            resource_id=allocation.id,
            previous_value={
                "invoice_id": allocation.invoice_id,
                "amount": str(allocation.amount),
            },
        )
        await self.session.delete(allocation)
        await self.session.commit()

    async def reconcile(
        self, organization_id: str, payment_id: str
    ) -> SupplierPaymentReconciliationResponse:
        payment = await self.session.scalar(
            select(SupplierPayment).where(
                SupplierPayment.organization_id == organization_id,
                SupplierPayment.id == payment_id,
            )
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Supplier payment not found")
        allocated = Decimal(
            await self.session.scalar(
                select(
                    func.coalesce(func.sum(SupplierPaymentAllocation.amount), 0)
                ).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.payment_id == payment_id,
                )
            )
            or 0
        ).quantize(CENT)
        unapplied = (Decimal(payment.amount) - allocated).quantize(CENT)
        return SupplierPaymentReconciliationResponse(
            payment_id=payment.id,
            organization_id=organization_id,
            payment_amount=Decimal(payment.amount),
            allocated_amount=allocated,
            unapplied_amount=unapplied,
            allocation_count=int(
                await self.session.scalar(
                    select(func.count(SupplierPaymentAllocation.id)).where(
                        SupplierPaymentAllocation.organization_id == organization_id,
                        SupplierPaymentAllocation.payment_id == payment_id,
                    )
                )
                or 0
            ),
            status="FULLY_ALLOCATED"
            if unapplied == 0
            else "PARTIALLY_ALLOCATED"
            if allocated
            else "UNAPPLIED",
        )
