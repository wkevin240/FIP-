from datetime import date
from decimal import Decimal

from app.models.invoicing.invoice import Invoice
from app.schemas.invoicing.collections import CollectionItem, CollectionSummary
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def classify_collection(as_of: date, due_date: date | None) -> tuple[int, str, str]:
    if due_date is None:
        return 0, "NO_DUE_DATE", "REVIEW"
    days_overdue = max((as_of - due_date).days, 0)
    if days_overdue == 0:
        return days_overdue, "CURRENT", "NORMAL"
    if days_overdue <= 30:
        return days_overdue, "1_30", "HIGH"
    if days_overdue <= 60:
        return days_overdue, "31_60", "HIGH"
    if days_overdue <= 90:
        return days_overdue, "61_90", "CRITICAL"
    return days_overdue, "90_PLUS", "CRITICAL"


class CollectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(
        self,
        organization_id: str,
        as_of: date,
        customer_name: str | None = None,
        overdue_only: bool = False,
    ) -> CollectionSummary:
        query = select(Invoice).where(
            Invoice.organization_id == organization_id,
            Invoice.status.in_(["ISSUED", "PARTIALLY_PAID"]),
        )
        if customer_name:
            query = query.where(Invoice.customer_name.ilike(f"%{customer_name}%"))
        invoices = list(
            (
                await self.session.scalars(
                    query.order_by(Invoice.due_date, Invoice.invoice_number)
                )
            ).all()
        )
        items: list[CollectionItem] = []
        for invoice in invoices:
            outstanding = invoice.outstanding_amount
            if outstanding <= Decimal("0.00"):
                continue
            days_overdue, bucket, priority = classify_collection(
                as_of, invoice.due_date
            )
            if overdue_only and days_overdue == 0:
                continue
            items.append(
                CollectionItem(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    customer_name=invoice.customer_name,
                    due_date=invoice.due_date,
                    total_amount=Decimal(invoice.total_amount),
                    paid_amount=Decimal(invoice.paid_amount),
                    credited_amount=Decimal(invoice.credited_amount),
                    outstanding_amount=outstanding,
                    days_overdue=days_overdue,
                    ageing_bucket=bucket,
                    priority=priority,
                )
            )
        overdue = sum(
            (item.outstanding_amount for item in items if item.days_overdue > 0),
            Decimal("0.00"),
        )
        total = sum((item.outstanding_amount for item in items), Decimal("0.00"))
        return CollectionSummary(
            organization_id=organization_id,
            as_of=as_of,
            status="READY" if items else "NOT_READY",
            total_outstanding=total.quantize(Decimal("0.01")),
            overdue_outstanding=overdue.quantize(Decimal("0.01")),
            item_count=len(items),
            items=items,
            blockers=[] if items else ["NO_OPEN_RECEIVABLES"],
        )
