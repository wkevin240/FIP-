from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class JournalEntryLine(Base):
    """One debit or credit line of a journal entry."""

    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        UniqueConstraint(
            "journal_entry_id",
            "line_number",
            name="uq_journal_entry_line_number",
        ),
        CheckConstraint("debit >= 0", name="ck_journal_entry_line_debit_non_negative"),
        CheckConstraint(
            "credit >= 0", name="ck_journal_entry_line_credit_non_negative"
        ),
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_journal_entry_line_single_side_amount",
        ),
    )

    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    line_number = Column(Integer, nullable=False)
    description = Column(String(500), nullable=True)
    debit = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    credit = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")
