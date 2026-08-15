from decimal import Decimal

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


class VATDeclaration(Base):
    """Computed VAT declaration snapshot for one organization and fiscal period."""

    __tablename__ = "vat_declarations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "fiscal_period_id",
            name="uq_vat_declaration_organization_period",
        ),
        CheckConstraint(
            "status IN ('READY', 'SUBMITTED')", name="ck_vat_declaration_status"
        ),
        CheckConstraint(
            "total_output_vat >= 0", name="ck_vat_declaration_output_non_negative"
        ),
        CheckConstraint(
            "total_input_vat >= 0", name="ck_vat_declaration_input_non_negative"
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
    status = Column(String(16), nullable=False, default="READY")
    total_output_vat = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    total_input_vat = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    net_vat_payable = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submitted_by_user_id = Column(String, nullable=True)

    organization = relationship("Organization")
    fiscal_period = relationship("FiscalPeriod")
