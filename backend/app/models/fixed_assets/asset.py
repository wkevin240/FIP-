from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class FixedAsset(Base):
    __tablename__ = "fixed_assets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "asset_code", name="uq_fixed_asset_organization_code"
        ),
        CheckConstraint(
            "acquisition_cost >= 0", name="ck_fixed_asset_cost_non_negative"
        ),
        CheckConstraint(
            "residual_value >= 0 AND residual_value <= acquisition_cost",
            name="ck_fixed_asset_residual_value",
        ),
        CheckConstraint(
            "available_for_use_date IS NULL OR available_for_use_date >= acquisition_date",
            name="ck_fixed_asset_available_date",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACQUIRED', 'IN_SERVICE', 'DISPOSED')",
            name="ck_fixed_asset_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id = Column(
        String,
        ForeignKey("fixed_asset_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    serial_number = Column(String(128), nullable=True)
    acquisition_date = Column(Date, nullable=False, index=True)
    available_for_use_date = Column(Date, nullable=True, index=True)
    acquisition_cost = Column(Numeric(18, 2), nullable=False)
    residual_value = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    currency = Column(String(3), nullable=False, default="XAF")
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    acquisition_journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    notes = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="fixed_assets")
    category = relationship("FixedAssetCategory", back_populates="assets")
    components = relationship("FixedAssetComponent", back_populates="asset")
    plans = relationship("DepreciationPlan", back_populates="asset")
    disposals = relationship("FixedAssetDisposal", back_populates="asset")


class FixedAssetComponent(Base):
    __tablename__ = "fixed_asset_components"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "component_code", name="uq_fixed_asset_component_code"
        ),
        CheckConstraint("acquisition_cost >= 0", name="ck_fixed_asset_component_cost"),
        CheckConstraint(
            "residual_value >= 0 AND residual_value <= acquisition_cost",
            name="ck_fixed_asset_component_residual_value",
        ),
        CheckConstraint(
            "useful_life_months > 0", name="ck_fixed_asset_component_useful_life"
        ),
        CheckConstraint(
            "method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_component_method",
        ),
        CheckConstraint(
            "declining_rate IS NULL OR (declining_rate > 0 AND declining_rate <= 100)",
            name="ck_fixed_asset_component_declining_rate",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name="ck_fixed_asset_component_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        String,
        ForeignKey("fixed_assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    component_code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    acquisition_cost = Column(Numeric(18, 2), nullable=False)
    residual_value = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    useful_life_months = Column(Integer, nullable=False)
    method = Column(String(32), nullable=False)
    declining_rate = Column(Numeric(9, 6), nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)

    asset = relationship("FixedAsset", back_populates="components")
    plans = relationship("DepreciationPlan", back_populates="component")
