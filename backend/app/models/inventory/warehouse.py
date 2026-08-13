from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Warehouse(Base):
    """Physical or logical storage location owned by one organization."""

    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "code", name="uq_warehouse_organization_code"
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
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="warehouses")
    stock_balances = relationship("StockBalance", back_populates="warehouse")
    stock_movements = relationship("StockMovement", back_populates="warehouse")
