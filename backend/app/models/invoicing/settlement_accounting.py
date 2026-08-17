from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class CreditNoteAccountingPosting(Base):
    __tablename__ = "credit_note_accounting_postings"
    __table_args__ = (
        CheckConstraint("source_module = 'INVOICING'", name="ck_cn_acc_source_module"),
        CheckConstraint("source_type = 'CREDIT_NOTE'", name="ck_cn_acc_source_type"),
        CheckConstraint("status = 'POSTED'", name="ck_cn_acc_status"),
        UniqueConstraint("organization_id", "source_id", name="uq_cn_acc_source"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_cn_acc_key"),
        UniqueConstraint("organization_id", "journal_entry_id", name="uq_cn_acc_entry"),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["credit_notes.organization_id", "credit_notes.id"],
            name="fk_cn_acc_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_cn_acc_entry",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    source_module = Column(String(64), nullable=False, default="INVOICING")
    source_type = Column(String(64), nullable=False, default="CREDIT_NOTE")
    source_id = Column(String, nullable=False)
    journal_entry_id = Column(String, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")


class PaymentAccountingPosting(Base):
    __tablename__ = "payment_accounting_postings"
    __table_args__ = (
        CheckConstraint("source_module = 'INVOICING'", name="ck_pay_acc_source_module"),
        CheckConstraint("source_type = 'PAYMENT'", name="ck_pay_acc_source_type"),
        CheckConstraint("status = 'POSTED'", name="ck_pay_acc_status"),
        UniqueConstraint("organization_id", "source_id", name="uq_pay_acc_source"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_pay_acc_key"),
        UniqueConstraint(
            "organization_id", "journal_entry_id", name="uq_pay_acc_entry"
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["payments.organization_id", "payments.id"],
            name="fk_pay_acc_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_pay_acc_entry",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "settlement_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_pay_acc_settlement",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    source_module = Column(String(64), nullable=False, default="INVOICING")
    source_type = Column(String(64), nullable=False, default="PAYMENT")
    source_id = Column(String, nullable=False)
    journal_entry_id = Column(String, nullable=False)
    settlement_account_id = Column(String, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")
