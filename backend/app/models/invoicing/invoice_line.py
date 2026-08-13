from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class InvoiceLine(Base):
    """Frozen commercial line and tax calculation belonging to one invoice."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0", name="ck_invoice_line_unit_price_non_negative"
        ),
        CheckConstraint("tax_rate >= 0", name="ck_invoice_line_tax_rate_non_negative"),
        CheckConstraint("tax_rate <= 100", name="ck_invoice_line_tax_rate_maximum"),
        CheckConstraint(
            "line_subtotal >= 0", name="ck_invoice_line_subtotal_non_negative"
        ),
        CheckConstraint("tax_amount >= 0", name="ck_invoice_line_tax_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_invoice_line_total_non_negative"),
        CheckConstraint(
            "line_total = line_subtotal + tax_amount",
            name="ck_invoice_line_total_consistency",
        ),
        CheckConstraint("sort_order > 0", name="ck_invoice_line_sort_order_positive"),
    )

    invoice_id = Column(
        String,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        String,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    vat_rate_id = Column(
        String,
        ForeignKey("vat_rates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 3), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=False)
    line_subtotal = Column(Numeric(18, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), nullable=False)
    line_total = Column(Numeric(18, 2), nullable=False)
    sort_order = Column(Integer, nullable=False)

    invoice = relationship("Invoice", back_populates="lines")
    product = relationship("Product")
    vat_rate = relationship("VATRate")
