from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class VATRate(Base):
    """Effective-dated VAT rate for one organization."""

    __tablename__ = "vat_rates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "code",
            "effective_from",
            name="uq_vat_rate_effective_code",
        ),
        CheckConstraint(
            "rate >= 0 AND rate <= 100", name="ck_vat_rate_percentage_range"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_vat_rate_effective_dates",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(32), nullable=False)
    name = Column(String(100), nullable=False)
    rate = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True)
    input_vat_account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    output_vat_account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="vat_rates")
    input_vat_account = relationship("Account", foreign_keys=[input_vat_account_id])
    output_vat_account = relationship("Account", foreign_keys=[output_vat_account_id])
    entries = relationship("VATEntry", back_populates="vat_rate")


class VATEntry(Base):
    """Tax calculation attached to one posted sales or purchase journal entry."""

    __tablename__ = "vat_entries"
    __table_args__ = (
        UniqueConstraint("journal_entry_id", name="uq_vat_entry_journal_entry"),
        CheckConstraint(
            "taxable_amount >= 0", name="ck_vat_entry_taxable_non_negative"
        ),
        CheckConstraint("vat_amount >= 0", name="ck_vat_entry_amount_non_negative"),
        CheckConstraint(
            "direction IN ('INPUT', 'OUTPUT')", name="ck_vat_entry_direction"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vat_rate_id = Column(
        String,
        ForeignKey("vat_rates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    direction = Column(String(16), nullable=False)
    tax_date = Column(Date, nullable=False, index=True)
    taxable_amount = Column(Numeric(18, 2), nullable=False)
    vat_amount = Column(Numeric(18, 2), nullable=False)

    organization = relationship("Organization", back_populates="vat_entries")
    vat_rate = relationship("VATRate", back_populates="entries")
    journal_entry = relationship("JournalEntry", back_populates="vat_entry")
