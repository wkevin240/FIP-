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

from app.core.enums.accounting import FiscalYearStatus
from app.db.base import Base


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_fiscal_year_organization_name"
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_fiscal_years_organization_id_id"
        ),
        CheckConstraint("end_date > start_date", name="ck_fiscal_year_dates"),
    )

    name = Column(String(100), index=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        SQLEnum(FiscalYearStatus), default=FiscalYearStatus.OPEN, nullable=False
    )

    organization = relationship("Organization", back_populates="fiscal_years")
    periods = relationship(
        "FiscalPeriod",
        back_populates="fiscal_year",
        cascade="all, delete-orphan",
        foreign_keys="FiscalPeriod.fiscal_year_id",
    )
