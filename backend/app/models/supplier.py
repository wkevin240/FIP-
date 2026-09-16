from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, String, UniqueConstraint, true
from sqlalchemy.orm import relationship

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_supplier_organization_id"),
        UniqueConstraint("organization_id", "code", name="uq_supplier_organization_code"),
        UniqueConstraint("organization_id", "tax_id", name="uq_supplier_organization_tax_id"),
        Index("ix_suppliers_organization_active_code", "organization_id", "is_active", "code"),
        CheckConstraint("btrim(code) <> ''", name="ck_suppliers_code_not_blank").ddl_if(dialect="postgresql"),
        CheckConstraint("code !~ '\\s'", name="ck_suppliers_code_no_whitespace").ddl_if(dialect="postgresql"),
        CheckConstraint("btrim(code) = code AND code = upper(code)", name="ck_suppliers_code_canonical").ddl_if(dialect="postgresql"),
        CheckConstraint("btrim(legal_name) <> ''", name="ck_suppliers_legal_name_not_blank").ddl_if(dialect="postgresql"),
    )

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    tax_id = Column(String(100), nullable=True)
    email = Column(String(320), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, server_default=true(), nullable=False)
    created_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    updated_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
