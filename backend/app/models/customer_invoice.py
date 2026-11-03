from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class CustomerInvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"


class CustomerInvoice(Base):
    __tablename__ = "customer_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_customer_invoice_organization_number"),
        UniqueConstraint("organization_id", "id", name="uq_customer_invoices_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_customer_invoices_organization_customer",
            ondelete="RESTRICT",
        ),
        CheckConstraint("btrim(invoice_number) <> ''", name="ck_customer_invoices_number_not_blank").ddl_if(dialect="postgresql"),
        CheckConstraint("length(currency_code) = 3 AND currency_code = upper(currency_code) AND currency_code NOT GLOB '*[^A-Z]*'", name="ck_customer_invoices_currency_canonical").ddl_if(dialect="postgresql"),
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount > 0", name="ck_customer_invoices_amounts_nonnegative").ddl_if(dialect="postgresql"),
        CheckConstraint("subtotal + tax_amount = total_amount", name="ck_customer_invoices_total_matches_components").ddl_if(dialect="postgresql"),
        CheckConstraint("due_date >= invoice_date", name="ck_customer_invoices_due_date").ddl_if(dialect="postgresql"),
        CheckConstraint(
            "(status = 'DRAFT' AND issued_by IS NULL AND issued_at IS NULL) OR "
            "(status = 'ISSUED' AND issued_by IS NOT NULL AND issued_at IS NOT NULL)",
            name="ck_customer_invoices_issue_metadata",
        ).ddl_if(dialect="postgresql"),
        Index("ix_customer_invoices_org_status_due_date", "organization_id", "status", "due_date"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    customer_id = Column(String, nullable=False)
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    currency_code = Column(String(3), nullable=False)
    subtotal = Column(Numeric(20, 2), nullable=False)
    tax_amount = Column(Numeric(20, 2), nullable=False)
    total_amount = Column(Numeric(20, 2), nullable=False)
    status = Column(
        SQLEnum(CustomerInvoiceStatus, native_enum=False, length=16),
        nullable=False,
        default=CustomerInvoiceStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )
    issued_at = Column(DateTime(timezone=True), nullable=True)
    issued_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    customer = relationship("Customer")
    issuer = relationship("User", foreign_keys=[issued_by])
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
