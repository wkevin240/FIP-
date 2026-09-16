from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_context import AuditContext
from app.domain.ap_aging import ApprovedExposureBucket, add_exposure, empty_bucket_totals
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceStatus
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.supplier_invoice_repository import SupplierInvoiceRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier_invoice import SupplierInvoiceCreate, SupplierInvoiceUpdate


class SupplierInvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierInvoiceRepository(session)
        self.supplier_repository = SupplierRepository(session)
        self.audit_repository = AuditLogRepository(session)

    @staticmethod
    def _audit_payload(invoice: SupplierInvoice) -> dict:
        return {
            "supplier_invoice_id": invoice.id,
            "supplier_id": invoice.supplier_id,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "currency_code": invoice.currency_code,
            "subtotal": invoice.subtotal,
            "tax_amount": invoice.tax_amount,
            "total_amount": invoice.total_amount,
            "description": invoice.description,
            "status": invoice.status.value if hasattr(invoice.status, "value") else invoice.status,
            "approved_by": invoice.approved_by,
            "approved_at": invoice.approved_at,
        }

    async def get(self, organization_id: str, invoice_id: str) -> SupplierInvoice:
        invoice = await self.repository.get_by_id(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
        return invoice

    async def list(self, organization_id: str, skip: int = 0, limit: int = 100, status_value: str | None = None, supplier_id: str | None = None) -> list[SupplierInvoice]:
        return await self.repository.list(organization_id, skip=skip, limit=limit, status=status_value, supplier_id=supplier_id)

    async def approved_exposure_aging(self, organization_id: str, as_of_date: date) -> list[dict]:
        invoices = await self.repository.list_approved_for_exposure(organization_id)
        grouped: dict[tuple[str, str], dict] = {}

        for invoice in invoices:
            key = (invoice.supplier_id, invoice.currency_code)
            row = grouped.setdefault(
                key,
                {
                    "supplier_id": invoice.supplier_id,
                    "supplier_name": invoice.supplier.legal_name,
                    "currency_code": invoice.currency_code,
                    "buckets": empty_bucket_totals(),
                },
            )
            add_exposure(
                row["buckets"],
                due_date=invoice.due_date,
                as_of_date=as_of_date,
                amount=Decimal(invoice.total_amount),
            )

        result = []
        for row in grouped.values():
            buckets = row["buckets"]
            result.append(
                {
                    "supplier_id": row["supplier_id"],
                    "supplier_name": row["supplier_name"],
                    "currency_code": row["currency_code"],
                    "current_amount": buckets[ApprovedExposureBucket.CURRENT],
                    "overdue_1_30_amount": buckets[ApprovedExposureBucket.OVERDUE_1_30],
                    "overdue_31_60_amount": buckets[ApprovedExposureBucket.OVERDUE_31_60],
                    "overdue_61_90_amount": buckets[ApprovedExposureBucket.OVERDUE_61_90],
                    "overdue_90_plus_amount": buckets[ApprovedExposureBucket.OVERDUE_90_PLUS],
                    "total_amount": sum(buckets.values(), Decimal("0.00")),
                }
            )
        return sorted(result, key=lambda row: (row["supplier_id"], row["currency_code"]))

    async def _require_active_supplier(self, organization_id: str, supplier_id: str) -> Supplier:
        supplier = await self.supplier_repository.get_by_id(organization_id, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        if not supplier.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier is inactive")
        return supplier

    async def create(self, organization_id: str, actor_id: str, data: SupplierInvoiceCreate) -> SupplierInvoice:
        await self._require_active_supplier(organization_id, data.supplier_id)
        if await self.repository.get_by_number(organization_id, data.supplier_id, data.invoice_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier invoice number already exists")
        invoice = SupplierInvoice(
            organization_id=organization_id,
            supplier_id=data.supplier_id,
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            currency_code=data.currency_code,
            subtotal=data.subtotal,
            tax_amount=data.tax_amount,
            total_amount=data.total_amount,
            description=data.description,
            status=SupplierInvoiceStatus.DRAFT,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.repository.add(invoice)
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="SUPPLIER_INVOICE_CREATED"),
                entity_type="supplier_invoice", entity_id=invoice.id, payload=self._audit_payload(invoice),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier invoice conflicts with existing data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(invoice)
        return invoice

    async def update(self, organization_id: str, invoice_id: str, actor_id: str, data: SupplierInvoiceUpdate) -> SupplierInvoice:
        invoice = await self.repository.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
        if invoice.status != SupplierInvoiceStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft supplier invoices can be edited")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return invoice
        if "invoice_number" in changes:
            duplicate = await self.repository.get_by_number(organization_id, invoice.supplier_id, changes["invoice_number"])
            if duplicate is not None and duplicate.id != invoice.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier invoice number already exists")
        proposed = {
            "invoice_date": changes.get("invoice_date", invoice.invoice_date),
            "due_date": changes.get("due_date", invoice.due_date),
            "subtotal": changes.get("subtotal", invoice.subtotal),
            "tax_amount": changes.get("tax_amount", invoice.tax_amount),
            "total_amount": changes.get("total_amount", invoice.total_amount),
        }
        if proposed["invoice_date"] > proposed["due_date"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Due date cannot be before invoice date")
        if proposed["total_amount"] != proposed["subtotal"] + proposed["tax_amount"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Total amount must equal subtotal plus tax amount")
        for field, value in changes.items():
            setattr(invoice, field, value)
        invoice.updated_by = actor_id
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="SUPPLIER_INVOICE_UPDATED"),
                entity_type="supplier_invoice", entity_id=invoice.id, payload=self._audit_payload(invoice),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Supplier invoice conflicts with existing data") from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(invoice)
        return invoice

    async def approve(self, organization_id: str, invoice_id: str, actor_id: str) -> SupplierInvoice:
        invoice = await self.repository.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
        if invoice.status != SupplierInvoiceStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft supplier invoices can be approved")
        if actor_id == invoice.created_by:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invoice creator cannot approve the same invoice")
        await self._require_active_supplier(organization_id, invoice.supplier_id)
        invoice.status = SupplierInvoiceStatus.APPROVED
        invoice.approved_by = actor_id
        invoice.approved_at = datetime.utcnow()
        invoice.updated_by = actor_id
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="SUPPLIER_INVOICE_APPROVED"),
                entity_type="supplier_invoice", entity_id=invoice.id, payload=self._audit_payload(invoice),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(invoice)
        return invoice

    async def cancel(self, organization_id: str, invoice_id: str, actor_id: str) -> SupplierInvoice:
        invoice = await self.repository.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
        if invoice.status == SupplierInvoiceStatus.CANCELLED:
            return invoice
        invoice.status = SupplierInvoiceStatus.CANCELLED
        invoice.approved_by = None
        invoice.approved_at = None
        invoice.updated_by = actor_id
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="SUPPLIER_INVOICE_CANCELLED"),
                entity_type="supplier_invoice", entity_id=invoice.id, payload=self._audit_payload(invoice),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(invoice)
        return invoice
