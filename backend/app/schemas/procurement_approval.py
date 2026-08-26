from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PurchaseInvoiceApprovalDecision(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: str | None = Field(default=None, max_length=500)


class PurchaseInvoiceApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: str
    purchase_invoice_id: str
    requester_user_id: str
    approver_user_id: str | None
    status: str
    reason: str | None
    decided_at: datetime | None
