from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class FixedAssetAccountingProfile(Base):
    __tablename__ = "fixed_asset_accounting_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "profile_code",
            name="uq_fixed_asset_accounting_profile_code",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    profile_code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    journal_id = Column(
        String,
        ForeignKey("journals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    accumulated_depreciation_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    depreciation_expense_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    acquisition_counterpart_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    disposal_proceeds_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    disposal_gain_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    disposal_loss_account_id = Column(
        String, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship(
        "Organization", back_populates="fixed_asset_accounting_profiles"
    )
    categories = relationship("FixedAssetCategory", back_populates="accounting_profile")


class FixedAssetCategory(Base):
    __tablename__ = "fixed_asset_categories"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "code", name="uq_fixed_asset_category_organization_code"
        ),
        CheckConstraint(
            "default_useful_life_months > 0",
            name="ck_fixed_asset_category_useful_life_positive",
        ),
        CheckConstraint(
            "default_residual_rate >= 0 AND default_residual_rate <= 100",
            name="ck_fixed_asset_category_residual_rate",
        ),
        CheckConstraint(
            "default_declining_rate IS NULL OR (default_declining_rate > 0 AND default_declining_rate <= 100)",
            name="ck_fixed_asset_category_declining_rate",
        ),
        CheckConstraint(
            "default_method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_category_method",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    accounting_profile_id = Column(
        String,
        ForeignKey("fixed_asset_accounting_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    default_method = Column(String(32), nullable=False, default="STRAIGHT_LINE")
    default_useful_life_months = Column(Integer, nullable=False)
    default_residual_rate = Column(
        Numeric(9, 6), nullable=False, default=Decimal("0.000000")
    )
    default_declining_rate = Column(Numeric(9, 6), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="fixed_asset_categories")
    accounting_profile = relationship(
        "FixedAssetAccountingProfile", back_populates="categories"
    )
    assets = relationship("FixedAsset", back_populates="category")
