from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "supplier_code", name="uq_supplier_org_code"
        ),
        UniqueConstraint("organization_id", "id", name="uq_supplier_org_id"),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_code = Column(String(64), nullable=False)
    legal_name = Column(String(255), nullable=False)
    tax_id = Column(String(64), nullable=True)
    address = Column(Text, nullable=True)
    currency = Column(String(3), nullable=False, default="XOF")
    is_active = Column(Boolean, nullable=False, default=True)

    invoices = relationship("PurchaseInvoice", back_populates="supplier")


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "invoice_number", name="uq_purchase_invoice_org_number"
        ),
        UniqueConstraint("organization_id", "id", name="uq_purchase_invoice_org_id"),
        CheckConstraint(
            "subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0",
            name="ck_purchase_invoice_amounts_non_negative",
        ),
        CheckConstraint(
            "total_amount = subtotal + tax_amount",
            name="ck_purchase_invoice_total_consistency",
        ),
        CheckConstraint(
            "paid_amount >= 0 AND paid_amount <= total_amount",
            name="ck_purchase_invoice_paid_bounds",
        ),
        CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_purchase_invoice_due_date",
        ),
        CheckConstraint(
            "status IN ('DRAFT','VALIDATED','PARTIALLY_PAID','PAID','CANCELLED')",
            name="ck_purchase_invoice_status",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_purchase_invoice_org_supplier",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id = Column(String, nullable=False, index=True)
    invoice_number = Column(String(64), nullable=False)
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True, index=True)
    currency = Column(String(3), nullable=False, default="XOF")
    status = Column(String(24), nullable=False, default="DRAFT", index=True)
    subtotal = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    paid_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    notes = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="invoices")
    lines = relationship(
        "PurchaseInvoiceLine", back_populates="invoice", cascade="all, delete-orphan"
    )
    payments = relationship("SupplierPayment", back_populates="invoice")
    payment_allocations = relationship(
        "SupplierPaymentAllocation", back_populates="invoice"
    )

    @property
    def outstanding_amount(self) -> Decimal:
        return (Decimal(self.total_amount) - Decimal(self.paid_amount)).quantize(
            Decimal("0.01")
        )


class PurchaseInvoiceLine(Base):
    __tablename__ = "purchase_invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_line_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0 AND tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_line_values",
        ),
        CheckConstraint(
            "line_subtotal >= 0 AND tax_amount >= 0 AND line_total = line_subtotal + tax_amount",
            name="ck_purchase_line_totals",
        ),
        CheckConstraint("sort_order > 0", name="ck_purchase_line_sort_order"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_purchase_line_org_invoice",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(String, nullable=False, index=True)
    expense_account_id = Column(String, nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 3), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=False)
    line_subtotal = Column(Numeric(18, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), nullable=False)
    line_total = Column(Numeric(18, 2), nullable=False)
    sort_order = Column(Integer, nullable=False)

    invoice = relationship("PurchaseInvoice", back_populates="lines")


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_supplier_payment_org_external",
        ),
        UniqueConstraint("organization_id", "id", name="uq_supplier_payment_org_id"),
        CheckConstraint("amount > 0", name="ck_supplier_payment_amount_positive"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_supplier_payment_org_invoice",
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
    external_reference = Column(String(128), nullable=False)
    notes = Column(Text, nullable=True)

    invoice = relationship("PurchaseInvoice", back_populates="payments")
    allocations = relationship(
        "SupplierPaymentAllocation",
        back_populates="payment",
        overlaps="payment_allocations",
    )


class ProcurementAccountingProfile(Base):
    __tablename__ = "procurement_accounting_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_procurement_profile_org"),
        ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_procurement_profile_org_journal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "payable_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_payable",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "deductible_vat_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_vat",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "settlement_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_settlement",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_id = Column(String, nullable=False)
    payable_account_id = Column(String, nullable=False)
    deductible_vat_account_id = Column(String, nullable=True)
    settlement_account_id = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class PurchaseInvoiceAccountingPosting(Base):
    __tablename__ = "purchase_invoice_accounting_postings"
    __table_args__ = (
        CheckConstraint(
            "source_module = 'PROCUREMENT' AND source_type = 'PURCHASE_INVOICE' AND status = 'POSTED'",
            name="ck_purchase_posting_identity",
        ),
        UniqueConstraint(
            "organization_id", "source_id", name="uq_purchase_posting_source"
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_purchase_posting_key"
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_purchase_posting_org_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_purchase_posting_org_entry",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_module = Column(String(64), nullable=False, default="PROCUREMENT")
    source_type = Column(String(64), nullable=False, default="PURCHASE_INVOICE")
    source_id = Column(String, nullable=False, index=True)
    journal_entry_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")


class SupplierPaymentAccountingPosting(Base):
    __tablename__ = "supplier_payment_accounting_postings"
    __table_args__ = (
        CheckConstraint(
            "source_module = 'PROCUREMENT' AND source_type = 'SUPPLIER_PAYMENT' AND status = 'POSTED'",
            name="ck_supplier_payment_posting_identity",
        ),
        UniqueConstraint(
            "organization_id", "source_id", name="uq_supplier_payment_posting_source"
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_supplier_payment_posting_key"
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["supplier_payments.organization_id", "supplier_payments.id"],
            name="fk_supplier_payment_posting_org_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_supplier_payment_posting_org_entry",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_module = Column(String(64), nullable=False, default="PROCUREMENT")
    source_type = Column(String(64), nullable=False, default="SUPPLIER_PAYMENT")
    source_id = Column(String, nullable=False, index=True)
    journal_entry_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")
