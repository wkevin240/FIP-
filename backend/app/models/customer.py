from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_customer_organization_code"),
        UniqueConstraint("organization_id", "tax_id", name="uq_customer_organization_tax_id"),
        CheckConstraint("btrim(code) <> ''", name="ck_customers_code_not_blank"),
        CheckConstraint("code !~ '\\s'", name="ck_customers_code_no_whitespace"),
        CheckConstraint("btrim(legal_name) <> ''", name="ck_customers_legal_name_not_blank"),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(50), nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    tax_id = Column(String(100), nullable=True)
    email = Column(String(320), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    updated_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
