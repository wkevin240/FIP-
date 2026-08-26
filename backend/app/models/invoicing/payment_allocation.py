from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_payment_allocations_org_id"),
        UniqueConstraint(
            "organization_id",
            "payment_id",
            "invoice_id",
            name="uq_payment_allocation_payment_invoice",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_allocation_idempotency",
        ),
        CheckConstraint("amount > 0", name="ck_payment_allocation_positive"),
        ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["payments.organization_id", "payments.id"],
            name="fk_payment_allocation_payment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_payment_allocation_invoice",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id = Column(String, nullable=False, index=True)
    invoice_id = Column(String, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    allocated_at = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    allocated_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    payment = relationship(
        "Payment", back_populates="allocations", overlaps="payment_allocations"
    )
    invoice = relationship(
        "Invoice", back_populates="payment_allocations", overlaps="allocations,payment"
    )
