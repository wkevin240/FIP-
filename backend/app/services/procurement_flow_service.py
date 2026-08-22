from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.procurement import PurchaseInvoice
from app.models.procurement_flow import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
)
from app.schemas.procurement_flow import (
    GoodsReceiptCreate,
    PurchaseOrderCreate,
    PurchaseRequestCreate,
)
from app.services.audit.audit_service import AuditService


class ProcurementFlowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def create_request(
        self, organization_id: str, actor_user_id: str, data: PurchaseRequestCreate
    ):
        request = PurchaseRequest(
            organization_id=organization_id,
            request_number=data.request_number,
            requester_user_id=actor_user_id,
            purpose=data.purpose,
            status="DRAFT",
        )
        request.lines = [
            PurchaseRequestLine(organization_id=organization_id, **line.model_dump())
            for line in data.lines
        ]
        self.session.add(request)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_REQUEST_CREATED",
            resource_type="PurchaseRequest",
            resource_id=request.id,
            new_value={"request_number": request.request_number},
        )
        await self.session.commit()
        return request

    async def transition_request(
        self, organization_id: str, actor_user_id: str, request_id: str, target: str
    ):
        request = await self.session.scalar(
            select(PurchaseRequest)
            .where(
                PurchaseRequest.organization_id == organization_id,
                PurchaseRequest.id == request_id,
            )
            .options(selectinload(PurchaseRequest.lines))
            .with_for_update()
        )
        if request is None:
            raise HTTPException(404, "Purchase request not found")
        allowed = {
            "DRAFT": {"SUBMITTED"},
            "SUBMITTED": {"APPROVED", "REJECTED"},
            "REJECTED": {"SUBMITTED"},
        }
        if target not in allowed.get(request.status, set()):
            raise HTTPException(422, "Invalid purchase request transition")
        if target == "APPROVED" and request.requester_user_id == actor_user_id:
            raise HTTPException(403, "Requester cannot approve its own request")
        previous = request.status
        request.status = target
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=f"PURCHASE_REQUEST_{target}",
            resource_type="PurchaseRequest",
            resource_id=request.id,
            previous_value={"status": previous},
            new_value={"status": target},
        )
        await self.session.commit()
        return request

    async def create_order(
        self, organization_id: str, actor_user_id: str, data: PurchaseOrderCreate
    ):
        if data.request_id:
            request = await self.session.scalar(
                select(PurchaseRequest)
                .where(
                    PurchaseRequest.organization_id == organization_id,
                    PurchaseRequest.id == data.request_id,
                )
                .with_for_update()
            )
            if request is None or request.status != "APPROVED":
                raise HTTPException(422, "An approved purchase request is required")
        order = PurchaseOrder(
            organization_id=organization_id, **data.model_dump(exclude={"lines"})
        )
        order.lines = [
            PurchaseOrderLine(organization_id=organization_id, **line.model_dump())
            for line in data.lines
        ]
        self.session.add(order)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_ORDER_CREATED",
            resource_type="PurchaseOrder",
            resource_id=order.id,
            new_value={
                "order_number": order.order_number,
                "supplier_id": order.supplier_id,
            },
        )
        await self.session.commit()
        return order

    async def issue_order(
        self, organization_id: str, actor_user_id: str, order_id: str
    ):
        order = await self.session.scalar(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.id == order_id,
            )
            .options(selectinload(PurchaseOrder.lines))
            .with_for_update()
        )
        if order is None:
            raise HTTPException(404, "Purchase order not found")
        if order.status != "DRAFT" or not order.lines:
            raise HTTPException(422, "Only a non-empty draft order can be issued")
        order.status = "ISSUED"
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_ORDER_ISSUED",
            resource_type="PurchaseOrder",
            resource_id=order.id,
            previous_value={"status": "DRAFT"},
            new_value={"status": "ISSUED"},
        )
        await self.session.commit()
        return order

    async def create_receipt(
        self, organization_id: str, actor_user_id: str, data: GoodsReceiptCreate
    ):
        order = await self.session.scalar(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.id == data.order_id,
            )
            .options(selectinload(PurchaseOrder.lines))
            .with_for_update()
        )
        if order is None or order.status != "ISSUED":
            raise HTTPException(422, "Only an issued purchase order can be received")
        line_ids = {line.id for line in order.lines}
        if any(line.order_line_id not in line_ids for line in data.lines):
            raise HTTPException(422, "Receipt line does not belong to purchase order")
        submitted_line_ids = [line.order_line_id for line in data.lines]
        if len(submitted_line_ids) != len(set(submitted_line_ids)):
            raise HTTPException(422, "A receipt cannot contain duplicate order lines")
        received_rows = await self.session.execute(
            select(
                GoodsReceiptLine.order_line_id,
                func.coalesce(func.sum(GoodsReceiptLine.received_quantity), 0),
            )
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
            .where(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.order_id == order.id,
                GoodsReceipt.status == "POSTED",
                GoodsReceiptLine.organization_id == organization_id,
            )
            .group_by(GoodsReceiptLine.order_line_id)
        )
        received_by_line = {
            line_id: Decimal(quantity or 0) for line_id, quantity in received_rows.all()
        }
        ordered_by_line = {line.id: Decimal(line.quantity) for line in order.lines}
        for receipt_line in data.lines:
            total_received = received_by_line.get(
                receipt_line.order_line_id, Decimal(0)
            )
            if (
                total_received + Decimal(receipt_line.received_quantity)
                > ordered_by_line[receipt_line.order_line_id]
            ):
                raise HTTPException(422, "Received quantity exceeds ordered quantity")
        receipt = GoodsReceipt(
            organization_id=organization_id,
            receiver_user_id=actor_user_id,
            status="POSTED",
            **data.model_dump(exclude={"lines"}),
        )
        receipt.lines = [
            GoodsReceiptLine(organization_id=organization_id, **line.model_dump())
            for line in data.lines
        ]
        self.session.add(receipt)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="GOODS_RECEIPT_POSTED",
            resource_type="GoodsReceipt",
            resource_id=receipt.id,
            new_value={"order_id": order.id, "receipt_number": receipt.receipt_number},
        )
        await self.session.commit()
        return receipt

    async def three_way_match(self, organization_id: str, invoice_id: str):
        invoice = await self.session.scalar(
            select(PurchaseInvoice)
            .options(selectinload(PurchaseInvoice.lines))
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.id == invoice_id,
            )
        )
        if invoice is None or invoice.purchase_order_id is None:
            return {
                "status": "NOT_READY",
                "organization_id": organization_id,
                "purchase_order_id": None,
                "purchase_invoice_id": invoice_id,
                "ordered_amount": None,
                "received_amount": None,
                "invoiced_amount": None,
                "ordered_quantity": None,
                "received_quantity": None,
                "invoiced_quantity": None,
                "amount_difference": None,
                "quantity_difference": None,
                "blockers": ["PURCHASE_ORDER_LINK_MISSING"],
            }
        order = await self.session.scalar(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.id == invoice.purchase_order_id,
            )
            .options(selectinload(PurchaseOrder.lines))
        )
        if order is None:
            return {
                "status": "NOT_READY",
                "organization_id": organization_id,
                "purchase_order_id": invoice.purchase_order_id,
                "purchase_invoice_id": invoice.id,
                "ordered_amount": None,
                "received_amount": None,
                "invoiced_amount": Decimal(invoice.total_amount),
                "ordered_quantity": None,
                "received_quantity": None,
                "invoiced_quantity": None,
                "amount_difference": None,
                "quantity_difference": None,
                "blockers": ["PURCHASE_ORDER_NOT_FOUND"],
            }
        ordered_qty = sum((Decimal(line.quantity) for line in order.lines), Decimal(0))
        ordered_amount = sum(
            (Decimal(line.quantity) * Decimal(line.unit_price) for line in order.lines),
            Decimal(0),
        ).quantize(Decimal("0.01"))
        receipt_rows = await self.session.execute(
            select(
                GoodsReceiptLine.order_line_id,
                func.coalesce(func.sum(GoodsReceiptLine.received_quantity), 0),
            )
            .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
            .where(
                GoodsReceipt.organization_id == organization_id,
                GoodsReceipt.order_id == order.id,
                GoodsReceipt.status == "POSTED",
                GoodsReceiptLine.organization_id == organization_id,
            )
            .group_by(GoodsReceiptLine.order_line_id)
        )
        received_by_line = {
            line_id: Decimal(quantity or 0) for line_id, quantity in receipt_rows.all()
        }
        received_qty = sum(received_by_line.values(), Decimal(0))
        ordered_by_sort = {line.sort_order: line for line in order.lines}
        invoice_by_sort = {line.sort_order: line for line in invoice.lines}
        relation_ready = bool(invoice.lines) and set(ordered_by_sort) == set(
            invoice_by_sort
        )
        received_amount = Decimal("0.00")
        if relation_ready:
            received_amount = sum(
                (
                    received_by_line.get(ordered_by_sort[sort_order].id, Decimal(0))
                    * Decimal(ordered_by_sort[sort_order].unit_price)
                    for sort_order in ordered_by_sort
                ),
                Decimal(0),
            ).quantize(Decimal("0.01"))
        invoiced_qty = (
            sum((Decimal(line.quantity) for line in invoice.lines), Decimal(0))
            if invoice.lines
            else None
        )
        invoiced_amount = Decimal(invoice.subtotal)
        amount_difference = (invoiced_amount - received_amount).quantize(
            Decimal("0.01")
        )
        quantity_difference = (
            None
            if invoiced_qty is None
            else (invoiced_qty - received_qty).quantize(Decimal("0.001"))
        )
        blockers = []
        if not relation_ready:
            blockers.append("INVOICE_ORDER_LINE_RELATION_MISSING")
        if received_qty == 0:
            blockers.append("NO_POSTED_RECEIPT")
        if amount_difference != 0:
            blockers.append("AMOUNT_MISMATCH")
        if quantity_difference is not None and quantity_difference > 0:
            blockers.append("QUANTITY_EXCEEDS_RECEIPT")
        match_status = (
            "MATCHED"
            if not blockers
            else (
                "PARTIAL"
                if received_qty > 0
                and "AMOUNT_MISMATCH" not in blockers
                and quantity_difference is not None
                and quantity_difference != 0
                else "MISMATCH"
            )
        )
        return {
            "status": match_status,
            "organization_id": organization_id,
            "purchase_order_id": order.id,
            "purchase_invoice_id": invoice.id,
            "ordered_amount": ordered_amount,
            "received_amount": received_amount,
            "invoiced_amount": invoiced_amount,
            "ordered_quantity": ordered_qty,
            "received_quantity": received_qty,
            "invoiced_quantity": invoiced_qty,
            "amount_difference": amount_difference,
            "quantity_difference": quantity_difference,
            "blockers": blockers,
        }
