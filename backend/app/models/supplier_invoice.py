from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, Column, Date, Enum as SQLEnum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class SupplierInvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "supplier_id", "invoice_number", name="uq_supplier_invoice_org_supplier_number"),
        CheckConstraint("btrim(invoice_number) <> ''", name="ck_supplier_invoice_number_not_blank").ddl_if(dialect="postgresql"),
        CheckConstraint("invoice_date <= due_date", name="ck_supplier_invoice_due_on_or_after_invoice"),
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0", name="ck_supplier_invoice_amounts_non_negative"),
        CheckConstraint("total_amount = subtotal + tax_amount", name="ck_supplier_invoice_total_matches_components"),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_supplier_invoice_supplier_same_organization",
            ondelete="RESTRICT",
        ),
        Index("ix_supplier_invoices_organization_status_date", "organization_id", "status", "invoice_date"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    supplier_id = Column(String, nullable=False, index=True)
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    currency_code = Column(String(3), nullable=False)
    subtotal = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(20, 2), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(SupplierInvoiceStatus), nullable=False, default=SupplierInvoiceStatus.DRAFT, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    updated_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    approved_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)

    organization = relationship("Organization")
    supplier = relationship("Supplier")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    approver = relationship("User", foreign_keys=[approved_by])
