from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    name = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    accounts = relationship("Account", back_populates="organization")
    fiscal_years = relationship("FiscalYear", back_populates="organization")
    fiscal_periods = relationship("FiscalPeriod", back_populates="organization")
    journals = relationship("Journal", back_populates="organization")
    journal_entries = relationship("JournalEntry", back_populates="organization")
    period_closings = relationship("PeriodClosing", back_populates="organization")
    bank_transactions = relationship("BankTransaction", back_populates="organization")
    bank_reconciliations = relationship(
        "BankReconciliation", back_populates="organization"
    )
