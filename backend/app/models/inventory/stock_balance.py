from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class StockBalance(Base):
    """Current valued quantity for one product in one warehouse."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "warehouse_id",
            "product_id",
            name="uq_stock_balance_organization_warehouse_product",
        ),
        CheckConstraint("quantity >= 0", name="ck_stock_balance_quantity_non_negative"),
        CheckConstraint(
            "total_value >= 0", name="ck_stock_balance_total_value_non_negative"
        ),
        CheckConstraint(
            "average_unit_cost >= 0",
            name="ck_stock_balance_average_cost_non_negative",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id = Column(
        String,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        String,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity = Column(Numeric(18, 3), nullable=False, default=Decimal("0.000"))
    total_value = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    average_unit_cost = Column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    organization = relationship("Organization", back_populates="stock_balances")
    warehouse = relationship("Warehouse", back_populates="stock_balances")
    product = relationship("Product", back_populates="stock_balances")
