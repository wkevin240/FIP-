from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class TreasuryBankAccount(Base):
    """Operational bank profile mapped to one existing ledger asset account."""

    __tablename__ = "treasury_bank_accounts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_treasury_bank_accounts_organization_id_id",
        ),
        UniqueConstraint(
            "organization_id",
            "ledger_account_id",
            name="uq_treasury_bank_account_ledger",
        ),
        UniqueConstraint(
            "organization_id",
            "account_number",
            name="uq_treasury_bank_account_number",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ledger_account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_name = Column(String(128), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(64), nullable=False)
    currency = Column(String(3), nullable=False, default="XOF")
    opening_balance = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    opening_date = Column(Date, nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="treasury_bank_accounts")
    ledger_account = relationship("Account")
