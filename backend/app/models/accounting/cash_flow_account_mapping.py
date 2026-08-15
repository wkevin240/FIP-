from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class CashFlowAccountMapping(Base):
    """Tenant-scoped configuration for direct-method cash-flow classification."""

    __tablename__ = "cash_flow_account_mappings"
    __table_args__ = (
        CheckConstraint(
            "(is_cash_account = true AND cash_flow_category IS NULL) "
            "OR (is_cash_account = false AND cash_flow_category "
            "IN ('OPERATING', 'INVESTING', 'FINANCING'))",
            name="ck_cash_flow_mapping_role",
        ),
        UniqueConstraint(
            "organization_id",
            "account_id",
            name="uq_cash_flow_mapping_organization_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_cash_flow_mapping_organization_account",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id = Column(String, nullable=False, index=True)
    is_cash_account = Column(Boolean, nullable=False, default=False)
    cash_flow_category = Column(String(32), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
