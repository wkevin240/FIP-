from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class LedgerPosting(Base):
    """Immutable accounting movement created exactly once from a posted journal line."""

    __tablename__ = "ledger_postings"
    __table_args__ = (
        UniqueConstraint("journal_entry_id", "journal_entry_line_id", name="uq_ledger_posting_source_line"),
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_posting_non_negative"),
        CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="ck_ledger_posting_one_side"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    fiscal_period_id = Column(String, ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False, index=True)
    journal_entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, index=True)
    journal_entry_line_id = Column(String, ForeignKey("journal_entry_lines.id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    posting_date = Column(Date, nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    debit = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))
    credit = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))

    journal_entry = relationship("JournalEntry")
    journal_entry_line = relationship("JournalEntryLine")
    account = relationship("Account")
