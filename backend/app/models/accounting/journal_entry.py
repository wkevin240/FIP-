from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class JournalEntryStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_journal_entry_org_idempotency"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    fiscal_period_id = Column(String, ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    reference = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(JournalEntryStatus), nullable=False, default=JournalEntryStatus.DRAFT, index=True)
    idempotency_key = Column(String(255), nullable=False)
    idempotency_hash = Column(String(64), nullable=False)
    posted_at = Column(DateTime, nullable=True)
    posted_by = Column(String, nullable=True)

    fiscal_period = relationship("FiscalPeriod")
    lines = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan", order_by="JournalEntryLine.line_number")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_entry_line_number"),
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_entry_line_non_negative"),
        CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="ck_journal_entry_line_one_side"),
    )

    journal_entry_id = Column(String, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    debit = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))
    credit = Column(Numeric(20, 2), nullable=False, default=Decimal("0.00"))

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")
