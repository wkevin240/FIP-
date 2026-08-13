from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class BankReconciliation(Base):
    """Auditable one-to-one match between a bank transaction and ledger entry."""

    __tablename__ = "bank_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "bank_transaction_id", name="uq_bank_reconciliation_transaction"
        ),
        UniqueConstraint("journal_entry_id", name="uq_bank_reconciliation_entry"),
        CheckConstraint(
            "matched_amount > 0", name="ck_bank_reconciliation_positive_amount"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_transaction_id = Column(
        String,
        ForeignKey("bank_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reconciled_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reconciled_at = Column(DateTime(timezone=True), nullable=False)
    matched_amount = Column(Numeric(18, 2), nullable=False)
    match_method = Column(String(32), nullable=False, default="MANUAL")

    organization = relationship("Organization", back_populates="bank_reconciliations")
    bank_transaction = relationship("BankTransaction", back_populates="reconciliation")
    journal_entry = relationship("JournalEntry", back_populates="bank_reconciliation")
    reconciled_by = relationship("User")
