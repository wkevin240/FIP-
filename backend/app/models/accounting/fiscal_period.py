from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
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
        CheckConstraint("end_date > start_date", name="ck_fiscal_period_dates"),
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

    fiscal_year = relationship("FiscalYear", back_populates="periods")
    organization = relationship("Organization", back_populates="fiscal_periods")
