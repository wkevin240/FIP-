from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.enums.accounting import FiscalPeriodStatus
from app.db.base import Base


class FiscalPeriod(Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "fiscal_year_id",
            "name",
            name="uq_fiscal_period_organization_year_name",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_fiscal_periods_organization_id_id",
        ),
        CheckConstraint("end_date > start_date", name="ck_fiscal_period_dates"),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_fiscal_periods_organization_year",
            ondelete="RESTRICT",
        ),
    )

    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(
        SQLEnum(FiscalPeriodStatus), default=FiscalPeriodStatus.OPEN, nullable=False
    )
    fiscal_year_id = Column(String, ForeignKey("fiscal_years.id"), nullable=False)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    fiscal_year = relationship(
        "FiscalYear", back_populates="periods", foreign_keys=[fiscal_year_id]
    )
    organization = relationship("Organization", back_populates="fiscal_periods")
    journal_entries = relationship(
        "JournalEntry",
        back_populates="fiscal_period",
        foreign_keys="JournalEntry.fiscal_period_id",
    )
    closing = relationship(
        "PeriodClosing", back_populates="fiscal_period", uselist=False
    )
