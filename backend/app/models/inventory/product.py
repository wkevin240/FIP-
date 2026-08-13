from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Product(Base):
    """Stock-tracked item owned by one organization."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_product_organization_sku"),
        CheckConstraint(
            "reorder_point >= 0", name="ck_product_reorder_point_non_negative"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(16), nullable=False, default="UNIT")
    reorder_point = Column(Numeric(18, 3), nullable=False, default=Decimal("0.000"))
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="products")
    stock_balances = relationship("StockBalance", back_populates="product")
    stock_movements = relationship("StockMovement", back_populates="product")
