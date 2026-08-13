from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PeriodClosing(Base):
    """Immutable audit record produced when an accounting period is closed."""

    __tablename__ = "period_closings"
    __table_args__ = (
        UniqueConstraint("fiscal_period_id", name="uq_period_closing_fiscal_period"),
        CheckConstraint(
            "posted_entry_count >= 0", name="ck_period_closing_entry_count_non_negative"
        ),
        CheckConstraint(
            "posted_line_count >= 0", name="ck_period_closing_line_count_non_negative"
        ),
        CheckConstraint(
            "total_debit >= 0", name="ck_period_closing_total_debit_non_negative"
        ),
        CheckConstraint(
            "total_credit >= 0", name="ck_period_closing_total_credit_non_negative"
        ),
        CheckConstraint(
            "total_debit = total_credit", name="ck_period_closing_totals_balance"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_period_id = Column(
        String,
        ForeignKey("fiscal_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    closed_by_user_id = Column(
        String,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    closed_at = Column(DateTime(timezone=True), nullable=False)
    posted_entry_count = Column(Integer, nullable=False)
    posted_line_count = Column(Integer, nullable=False)
    total_debit = Column(Numeric(18, 2), nullable=False)
    total_credit = Column(Numeric(18, 2), nullable=False)
    control_hash = Column(String(64), nullable=False)

    organization = relationship("Organization", back_populates="period_closings")
    fiscal_period = relationship("FiscalPeriod", back_populates="closing")
    closed_by = relationship("User")
