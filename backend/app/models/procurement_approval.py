from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class PurchaseInvoiceApproval(Base):
    __tablename__ = "purchase_invoice_approvals"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "purchase_invoice_id",
            name="uq_purchase_invoice_approval_org_invoice",
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_purchase_invoice_approval_status",
        ),
        CheckConstraint(
            "status = 'PENDING' OR decided_at IS NOT NULL",
            name="ck_purchase_invoice_approval_decided_at",
        ),
        CheckConstraint(
            "status = 'PENDING' OR approver_user_id IS NOT NULL",
            name="ck_purchase_invoice_approval_approver",
        ),
        CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> requester_user_id",
            name="ck_purchase_invoice_approval_separation",
        ),
        ForeignKeyConstraint(
            ["organization_id", "purchase_invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_purchase_invoice_approval_org_invoice",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_invoice_id = Column(String, nullable=False, index=True)
    requester_user_id = Column(String, nullable=False, index=True)
    approver_user_id = Column(String, nullable=True, index=True)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    reason = Column(String(500), nullable=True)
    decided_at = Column(DateTime, nullable=True)
