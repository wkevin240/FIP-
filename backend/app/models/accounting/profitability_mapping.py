from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProfitabilityAccountMapping(Base):
    """Versioned, tenant-scoped account classification for deterministic P&L."""

    __tablename__ = "profitability_account_mappings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "account_id",
            "rule_version",
            "effective_from",
            name="uq_profitability_mapping_scope_start",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_profitability_mapping_effective_range",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        String,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category = Column(String(64), nullable=False)
    rule_version = Column(String(64), nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)

    organization = relationship("Organization")
    account = relationship("Account")
