from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class CreditNote(Base):
    """Issued credit reducing the amount collectible on one invoice."""

    __tablename__ = "credit_notes"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_credit_notes_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id",
            "credit_note_number",
            name="uq_credit_note_organization_number",
        ),
        CheckConstraint("amount > 0", name="ck_credit_note_amount_positive"),
        CheckConstraint(
            "subtotal >= 0 AND tax_amount >= 0 AND amount = subtotal + tax_amount",
            name="ck_credit_note_amount_breakdown",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        String,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    credit_note_number = Column(String(64), nullable=False)
    credit_date = Column(Date, nullable=False, index=True)
    subtotal = Column(Numeric(18, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    reason = Column(String(500), nullable=False)
    issued_at = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="credit_notes")
    invoice = relationship("Invoice", back_populates="credit_notes")
