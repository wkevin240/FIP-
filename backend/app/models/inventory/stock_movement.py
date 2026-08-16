from sqlalchemy import (
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


class StockMovement(Base):
    """Immutable inventory movement used to derive current stock balances."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_stock_movements_organization_id_id"
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movement_quantity_positive"),
        CheckConstraint(
            "unit_cost >= 0", name="ck_stock_movement_unit_cost_non_negative"
        ),
        CheckConstraint(
            "total_value >= 0", name="ck_stock_movement_total_value_non_negative"
        ),
        CheckConstraint(
            "movement_type IN ('RECEIPT', 'ISSUE', 'ADJUSTMENT_IN', "
            "'ADJUSTMENT_OUT', 'TRANSFER_IN', 'TRANSFER_OUT')",
            name="ck_stock_movement_type",
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
    movement_type = Column(String(32), nullable=False, index=True)
    movement_date = Column(Date, nullable=False, index=True)
    quantity = Column(Numeric(18, 3), nullable=False)
    unit_cost = Column(Numeric(18, 4), nullable=False)
    total_value = Column(Numeric(18, 2), nullable=False)
    transfer_id = Column(String(36), nullable=True, index=True)
    reference = Column(String(100), nullable=True)
    note = Column(String(500), nullable=True)

    organization = relationship("Organization", back_populates="stock_movements")
    warehouse = relationship("Warehouse", back_populates="stock_movements")
    product = relationship("Product", back_populates="stock_movements")
