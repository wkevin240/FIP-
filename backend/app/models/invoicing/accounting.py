from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class InvoiceAccountingProfile(Base):
    """Organization-owned account mapping required before invoice posting."""

    __tablename__ = "invoice_accounting_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            name="uq_invoice_accounting_profile_organization",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_invoice_accounting_profiles_organization_id_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_inv_acc_profile_org_journal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "receivable_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_receivable",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "revenue_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_revenue",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "collected_vat_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_collected_vat",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_id = Column(String, nullable=False, index=True)
    receivable_account_id = Column(String, nullable=False)
    revenue_account_id = Column(String, nullable=False)
    collected_vat_account_id = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization")
    journal = relationship("Journal", foreign_keys=[journal_id])
    receivable_account = relationship("Account", foreign_keys=[receivable_account_id])
    revenue_account = relationship("Account", foreign_keys=[revenue_account_id])
    collected_vat_account = relationship(
        "Account", foreign_keys=[collected_vat_account_id]
    )


class InvoiceAccountingPosting(Base):
    """Immutable source-to-entry linkage for an invoice posting operation."""

    __tablename__ = "invoice_accounting_postings"
    __table_args__ = (
        CheckConstraint(
            "source_module = 'INVOICING'",
            name="ck_invoice_accounting_posting_source_module",
        ),
        CheckConstraint(
            "source_type = 'INVOICE'",
            name="ck_invoice_accounting_posting_source_type",
        ),
        CheckConstraint(
            "status = 'POSTED'",
            name="ck_invoice_accounting_posting_status",
        ),
        UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_invoice_accounting_posting_source",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_invoice_accounting_posting_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "journal_entry_id",
            name="uq_invoice_accounting_posting_journal_entry",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_inv_acc_post_org_invoice",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_inv_acc_post_org_journal_entry",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_module = Column(String(64), nullable=False, default="INVOICING")
    source_type = Column(String(64), nullable=False, default="INVOICE")
    source_id = Column(String, nullable=False, index=True)
    journal_entry_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")

    organization = relationship("Organization")
    invoice = relationship(
        "Invoice",
        back_populates="accounting_posting",
        foreign_keys=[source_id],
        uselist=False,
    )
    journal_entry = relationship("JournalEntry", foreign_keys=[journal_entry_id])
