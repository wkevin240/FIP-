from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


BALANCE_SHEET_CATEGORIES = ("ASSET", "LIABILITY", "EQUITY")


class BalanceSheetAccountMapping(Base):
    """Tenant-scoped, versioned classification used for balance-sheet reporting."""

    __tablename__ = "balance_sheet_account_mappings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "account_id",
            "rule_version",
            "effective_from",
            name="uq_balance_sheet_mapping_scope_start",
        ),
        CheckConstraint(
            "category IN ('ASSET', 'LIABILITY', 'EQUITY')",
            name="ck_balance_sheet_mapping_category",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_balance_sheet_mapping_effective_range",
        ),
        ExcludeConstraint(
            ("organization_id", "="),
            ("account_id", "="),
            ("rule_version", "="),
            (
                func.daterange("effective_from", "effective_to", "[]"),
                "&&",
            ),
            name="ex_balance_sheet_mapping_no_overlap",
        ).ddl_if(dialect="postgresql"),
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
    category = Column(String(16), nullable=False)
    rule_version = Column(String(64), nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)

    organization = relationship("Organization")
    account = relationship("Account")
