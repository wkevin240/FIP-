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


class ProfitabilityAccountMapping(Base):
    """Explicit organization-owned classification for profitability calculations."""

    __tablename__ = "profitability_account_mappings"
    __table_args__ = (
        CheckConstraint(
            "category IN ('REVENUE', 'COGS', 'OPERATING_EXPENSE', 'OTHER_INCOME', 'OTHER_EXPENSE')",
            name="ck_profitability_mapping_category",
        ),
        UniqueConstraint(
            "organization_id",
            "account_id",
            "category",
            name="uq_profitability_mapping_org_account_category",
        ),
        ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_profitability_mapping_org_account",
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
    category = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
