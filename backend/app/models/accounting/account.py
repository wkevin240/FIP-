from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_account_organization_code"),)

    organization_id = Column(String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(20), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    account_type = Column(String(50), nullable=False) # e.g. ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    parent_id = Column(String, ForeignKey("accounts.id"), nullable=True)
    collective_account_id = Column(String, ForeignKey("accounts.id"), nullable=True)
    level = Column(Integer, nullable=False, default=1)
    path = Column(String(500), nullable=False, default="/")

    organization = relationship("Organization", back_populates="accounts")
    parent = relationship("Account", remote_side="Account.id", backref="children")
