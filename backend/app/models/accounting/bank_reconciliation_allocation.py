from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class BankReconciliationBatch(Base):
    """An idempotent, tenant-scoped batch of partial bank-to-ledger allocations."""

    __tablename__ = "bank_reconciliation_batches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_bank_reconciliation_batches_org_id"
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_bank_reconciliation_batches_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bank_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_reconciliation_batches_org_account",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "allocated_total > 0",
            name="ck_bank_reconciliation_batches_positive_total",
        ),
    )

    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    bank_account_id = Column(String, nullable=False)
    reconciled_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reconciled_at = Column(DateTime(timezone=True), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    match_method = Column(String(32), nullable=False, default="MANUAL_PARTIAL")
    allocated_total = Column(Numeric(18, 2), nullable=False)

    organization = relationship("Organization", overlaps="bank_account")
    bank_account = relationship("Account", overlaps="organization")
    reconciled_by = relationship("User")
    allocations = relationship(
        "BankReconciliationAllocation",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BankReconciliationAllocation.id",
        overlaps="allocations,bank_transaction,journal_entry,organization",
    )


class BankReconciliationAllocation(Base):
    """An immutable positive allocation between one bank transaction and one entry."""

    __tablename__ = "bank_reconciliation_allocations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "batch_id",
            "bank_transaction_id",
            "journal_entry_id",
            name="uq_bank_reconciliation_allocation_batch_pair",
        ),
        ForeignKeyConstraint(
            ["organization_id", "batch_id"],
            [
                "bank_reconciliation_batches.organization_id",
                "bank_reconciliation_batches.id",
            ],
            name="fk_bank_reconciliation_allocations_org_batch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_reconciliation_allocations_org_transaction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_bank_reconciliation_allocations_org_entry",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "matched_amount > 0",
            name="ck_bank_reconciliation_allocations_positive_amount",
        ),
    )

    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id = Column(String, nullable=False)
    bank_transaction_id = Column(String, nullable=False)
    journal_entry_id = Column(String, nullable=False)
    matched_amount = Column(Numeric(18, 2), nullable=False)

    organization = relationship(
        "Organization", overlaps="allocations,batch,bank_transaction,journal_entry"
    )
    batch = relationship(
        "BankReconciliationBatch",
        back_populates="allocations",
        overlaps="bank_transaction,journal_entry,organization",
    )
    bank_transaction = relationship(
        "BankTransaction",
        back_populates="allocations",
        overlaps="batch,journal_entry,organization",
    )
    journal_entry = relationship(
        "JournalEntry",
        back_populates="bank_allocations",
        overlaps="batch,bank_transaction,organization",
    )
