from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "request_number", name="uq_purchase_request_org_number"
        ),
        UniqueConstraint("organization_id", "id", name="uq_purchase_request_org_id"),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','CANCELLED')",
            name="ck_purchase_request_status",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    request_number = Column(String(64), nullable=False)
    requester_user_id = Column(String(128), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="DRAFT", index=True)
    purpose = Column(Text, nullable=False)
    lines = relationship(
        "PurchaseRequestLine", cascade="all, delete-orphan", back_populates="request"
    )


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    request_id = Column(String, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 3), nullable=False)
    estimated_unit_price = Column(Numeric(18, 2), nullable=True)
    request = relationship("PurchaseRequest", back_populates="lines")
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_request_line_quantity"),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["purchase_requests.organization_id", "purchase_requests.id"],
            ondelete="RESTRICT",
        ),
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "order_number", name="uq_purchase_order_org_number"
        ),
        UniqueConstraint("organization_id", "id", name="uq_purchase_order_org_id"),
        CheckConstraint(
            "status IN ('DRAFT','ISSUED','CANCELLED','CLOSED')",
            name="ck_purchase_order_status",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["purchase_requests.organization_id", "purchase_requests.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id = Column(String, nullable=False, index=True)
    request_id = Column(String, nullable=True, index=True)
    order_number = Column(String(64), nullable=False)
    order_date = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT", index=True)
    lines = relationship(
        "PurchaseOrderLine", cascade="all, delete-orphan", back_populates="order"
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_order_line_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_purchase_order_line_price"),
        UniqueConstraint("organization_id", "id", name="uq_purchase_order_line_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["purchase_orders.organization_id", "purchase_orders.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id = Column(String, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(18, 3), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    sort_order = Column(Integer, nullable=False)
    order = relationship("PurchaseOrder", back_populates="lines")


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "receipt_number", name="uq_goods_receipt_org_number"
        ),
        UniqueConstraint("organization_id", "id", name="uq_goods_receipt_org_id"),
        CheckConstraint(
            "status IN ('DRAFT','POSTED','CANCELLED')", name="ck_goods_receipt_status"
        ),
        ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["purchase_orders.organization_id", "purchase_orders.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id = Column(String, nullable=False, index=True)
    receipt_number = Column(String(64), nullable=False)
    receipt_date = Column(Date, nullable=False)
    receiver_user_id = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT", index=True)
    lines = relationship(
        "GoodsReceiptLine", cascade="all, delete-orphan", back_populates="receipt"
    )


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        CheckConstraint("received_quantity > 0", name="ck_goods_receipt_line_quantity"),
        ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["goods_receipts.organization_id", "goods_receipts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "order_line_id"],
            ["purchase_order_lines.organization_id", "purchase_order_lines.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    receipt_id = Column(String, nullable=False, index=True)
    order_line_id = Column(String, nullable=False, index=True)
    received_quantity = Column(Numeric(18, 3), nullable=False)
    receipt = relationship("GoodsReceipt", back_populates="lines")
