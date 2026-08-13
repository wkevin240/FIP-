from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class BankTransaction(Base):
    """Imported bank statement transaction awaiting or holding reconciliation."""

    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "external_id",
            name="uq_bank_transaction_organization_account_external",
        ),
        CheckConstraint("amount <> 0", name="ck_bank_transaction_non_zero_amount"),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_date = Column(Date, nullable=False, index=True)
    value_date = Column(Date, nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    description = Column(String(500), nullable=False)
    reference = Column(String(100), nullable=True)
    external_id = Column(String(100), nullable=False)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="bank_transactions")
    bank_account = relationship("Account", back_populates="bank_transactions")
    reconciliation = relationship(
        "BankReconciliation",
        back_populates="bank_transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )
