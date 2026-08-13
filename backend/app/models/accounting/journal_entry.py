from sqlalchemy import Column, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.enums.accounting import JournalEntryStatus
from app.db.base import Base


class JournalEntry(Base):
    """A balanced accounting entry recorded in a tenant journal."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "journal_id",
            "entry_number",
            name="uq_journal_entry_organization_journal_number",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_id = Column(
        String,
        ForeignKey("journals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_period_id = Column(
        String,
        ForeignKey("fiscal_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_number = Column(String(50), nullable=False)
    entry_date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    reference = Column(String(100), nullable=True)
    status = Column(
        SQLEnum(JournalEntryStatus),
        nullable=False,
        default=JournalEntryStatus.DRAFT,
        index=True,
    )
    posted_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="journal_entries")
    journal = relationship("Journal", back_populates="entries")
    fiscal_period = relationship("FiscalPeriod", back_populates="journal_entries")
    lines = relationship(
        "JournalEntryLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalEntryLine.line_number",
    )
    bank_reconciliation = relationship(
        "BankReconciliation", back_populates="journal_entry", uselist=False
    )
    vat_entry = relationship("VATEntry", back_populates="journal_entry", uselist=False)
