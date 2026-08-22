from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Payment(Base):
    """Immutable payment applied to one issued invoice."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_payments_organization_id_id"
        ),
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "method IN ('CASH', 'BANK_TRANSFER', 'CARD', 'MOBILE_MONEY', 'OTHER')",
            name="ck_payment_method",
        ),
        UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_payment_organization_external",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_payment_org_invoice",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(String, nullable=True, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    method = Column(String(32), nullable=False)
    external_reference = Column(String(100), nullable=True)
    received_at = Column(DateTime, nullable=False)
    notes = Column(String(500), nullable=True)

    organization = relationship(
        "Organization", back_populates="payments", overlaps="payments"
    )
    invoice = relationship(
        "Invoice",
        back_populates="payments",
        overlaps="organization,payments,payment_allocations",
    )
    allocations = relationship(
        "PaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
        overlaps="payment_allocations",
    )
