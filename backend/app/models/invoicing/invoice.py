from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Invoice(Base):
    """Commercial invoice with immutable issued totals and a payment lifecycle."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "invoice_number", name="uq_invoice_organization_number"
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_invoices_organization_id_id"
        ),
        CheckConstraint("subtotal >= 0", name="ck_invoice_subtotal_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_invoice_tax_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_invoice_total_non_negative"),
        CheckConstraint(
            "total_amount = subtotal + tax_amount", name="ck_invoice_total_consistency"
        ),
        CheckConstraint("paid_amount >= 0", name="ck_invoice_paid_non_negative"),
        CheckConstraint(
            "paid_amount + credited_amount <= total_amount",
            name="ck_invoice_settlement_within_total",
        ),
        CheckConstraint(
            "credited_amount >= 0", name="ck_invoice_credited_non_negative"
        ),
        CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_invoice_due_date",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')",
            name="ck_invoice_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_number = Column(String(64), nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_tax_id = Column(String(64), nullable=True)
    customer_address = Column(Text, nullable=True)
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
    currency = Column(String(3), nullable=False, default="XOF")
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    subtotal = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    paid_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    credited_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    issued_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="invoices")
    lines = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan"
    )
    payments = relationship("Payment", back_populates="invoice")
    credit_notes = relationship("CreditNote", back_populates="invoice")
    accounting_posting = relationship(
        "InvoiceAccountingPosting",
        back_populates="invoice",
        uselist=False,
        foreign_keys="InvoiceAccountingPosting.source_id",
    )

    @property
    def outstanding_amount(self) -> Decimal:
        return (
            Decimal(self.total_amount)
            - Decimal(self.paid_amount)
            - Decimal(self.credited_amount)
        ).quantize(Decimal("0.01"))
