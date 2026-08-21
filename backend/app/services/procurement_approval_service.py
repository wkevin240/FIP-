from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procurement_approval import PurchaseInvoiceApproval
from app.repositories.procurement_repository import ProcurementRepository
from app.services.audit.audit_service import AuditService


class ProcurementApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProcurementRepository(session)
        self.audit = AuditService(session)

    async def request(
        self, organization_id: str, actor_user_id: str, invoice_id: str
    ) -> PurchaseInvoiceApproval:
        invoice = await self.repo.invoice(organization_id, invoice_id, lock=True)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Purchase invoice not found")
        if invoice.status != "VALIDATED":
            raise HTTPException(
                status_code=422,
                detail="Only validated purchase invoices can be submitted for approval",
            )
        existing = await self.session.scalar(
            select(PurchaseInvoiceApproval)
            .where(
                PurchaseInvoiceApproval.organization_id == organization_id,
                PurchaseInvoiceApproval.purchase_invoice_id == invoice_id,
            )
            .with_for_update()
        )
        if existing is not None:
            if existing.status == "REJECTED":
                raise HTTPException(
                    status_code=422,
                    detail="Rejected purchase invoice approval cannot be reused",
                )
            return existing
        approval = PurchaseInvoiceApproval(
            organization_id=organization_id,
            purchase_invoice_id=invoice.id,
            requester_user_id=actor_user_id,
            status="PENDING",
        )
        self.session.add(approval)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_INVOICE_APPROVAL_REQUESTED",
            resource_type="PurchaseInvoiceApproval",
            resource_id=approval.id,
            new_value={"purchase_invoice_id": invoice.id, "status": "PENDING"},
        )
        await self.session.commit()
        return approval

    async def decide(
        self,
        organization_id: str,
        actor_user_id: str,
        invoice_id: str,
        decision: str,
        reason: str | None = None,
    ) -> PurchaseInvoiceApproval:
        if decision not in {"APPROVED", "REJECTED"}:
            raise HTTPException(status_code=422, detail="Invalid approval decision")
        invoice = await self.repo.invoice(organization_id, invoice_id, lock=True)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Purchase invoice not found")
        approval = await self.session.scalar(
            select(PurchaseInvoiceApproval)
            .where(
                PurchaseInvoiceApproval.organization_id == organization_id,
                PurchaseInvoiceApproval.purchase_invoice_id == invoice_id,
            )
            .with_for_update()
        )
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if approval.requester_user_id == actor_user_id:
            raise HTTPException(
                status_code=403,
                detail="Requester cannot approve or reject its own invoice",
            )
        if approval.status != "PENDING":
            if approval.status == decision:
                return approval
            raise HTTPException(status_code=409, detail="Approval already decided")
        approval.status = decision
        approval.approver_user_id = actor_user_id
        approval.reason = reason.strip() if reason else None
        approval.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=f"PURCHASE_INVOICE_{decision}",
            resource_type="PurchaseInvoiceApproval",
            resource_id=approval.id,
            previous_value={"status": "PENDING"},
            new_value={
                "status": decision,
                "purchase_invoice_id": invoice.id,
                "reason": approval.reason,
            },
        )
        await self.session.commit()
        return approval

    async def get(
        self, organization_id: str, invoice_id: str
    ) -> PurchaseInvoiceApproval | None:
        return await self.session.scalar(
            select(PurchaseInvoiceApproval).where(
                PurchaseInvoiceApproval.organization_id == organization_id,
                PurchaseInvoiceApproval.purchase_invoice_id == invoice_id,
            )
        )

    async def require_approved(self, organization_id: str, invoice_id: str) -> None:
        approval = await self.get(organization_id, invoice_id)
        if approval is None or approval.status != "APPROVED":
            raise HTTPException(
                status_code=422,
                detail="Purchase invoice requires an approved control decision before posting",
            )
