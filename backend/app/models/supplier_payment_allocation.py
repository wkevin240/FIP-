from decimal import Decimal

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


class SupplierPaymentAllocation(Base):
    __tablename__ = "supplier_payment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "payment_id",
            "invoice_id",
            name="uq_supplier_payment_allocation_pair",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_supplier_payment_allocation_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["supplier_payments.organization_id", "supplier_payments.id"],
            name="fk_supplier_payment_allocation_org_payment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_supplier_payment_allocation_org_invoice",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_supplier_payment_allocation_org_supplier",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount > 0", name="ck_supplier_payment_allocation_positive"),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id = Column(String, nullable=False, index=True)
    invoice_id = Column(String, nullable=False, index=True)
    supplier_id = Column(String, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    payment = relationship(
        "SupplierPayment", back_populates="allocations", overlaps="payment_allocations"
    )
    invoice = relationship(
        "PurchaseInvoice",
        back_populates="payment_allocations",
        overlaps="allocations,payment",
    )
    supplier = relationship(
        "Supplier", overlaps="allocations,invoice,payment,payment_allocations"
    )

    @property
    def decimal_amount(self) -> Decimal:
        return Decimal(self.amount).quantize(Decimal("0.01"))
