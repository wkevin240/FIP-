from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class DepreciationPlan(Base):
    __tablename__ = "fixed_asset_depreciation_plans"
    __table_args__ = (
        UniqueConstraint(
            "component_id",
            "version_number",
            name="uq_fixed_asset_plan_component_version",
        ),
        CheckConstraint("version_number > 0", name="ck_fixed_asset_plan_version"),
        CheckConstraint(
            "useful_life_months > 0", name="ck_fixed_asset_plan_useful_life"
        ),
        CheckConstraint(
            "depreciable_base >= 0", name="ck_fixed_asset_plan_depreciable_base"
        ),
        CheckConstraint(
            "residual_value >= 0", name="ck_fixed_asset_plan_residual_value"
        ),
        CheckConstraint("end_date >= start_date", name="ck_fixed_asset_plan_dates"),
        CheckConstraint(
            "method IN ('STRAIGHT_LINE', 'DECLINING_BALANCE')",
            name="ck_fixed_asset_plan_method",
        ),
        CheckConstraint(
            "declining_rate IS NULL OR (declining_rate > 0 AND declining_rate <= 100)",
            name="ck_fixed_asset_plan_declining_rate",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'COMPLETED')",
            name="ck_fixed_asset_plan_status",
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
    component_id = Column(
        String,
        ForeignKey("fixed_asset_components.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    method = Column(String(32), nullable=False)
    useful_life_months = Column(Integer, nullable=False)
    declining_rate = Column(Numeric(9, 6), nullable=True)
    acquisition_cost = Column(Numeric(18, 2), nullable=False)
    residual_value = Column(Numeric(18, 2), nullable=False)
    depreciable_base = Column(Numeric(18, 2), nullable=False)
    convention = Column(String(32), nullable=False, default="MONTHLY_PRORATA_DIE")
    parameters_snapshot = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    activated_at = Column(DateTime, nullable=True)
    activated_by_user_id = Column(String, nullable=True)

    asset = relationship("FixedAsset", back_populates="plans")
    component = relationship("FixedAssetComponent", back_populates="plans")
    schedule_lines = relationship("DepreciationScheduleLine", back_populates="plan")


class DepreciationScheduleLine(Base):
    __tablename__ = "fixed_asset_depreciation_schedule_lines"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "sequence_number", name="uq_fixed_asset_schedule_plan_sequence"
        ),
        UniqueConstraint(
            "journal_entry_id", name="uq_fixed_asset_schedule_journal_entry"
        ),
        CheckConstraint("sequence_number > 0", name="ck_fixed_asset_schedule_sequence"),
        CheckConstraint(
            "depreciation_amount >= 0", name="ck_fixed_asset_schedule_amount"
        ),
        CheckConstraint(
            "opening_net_book_value >= 0", name="ck_fixed_asset_schedule_opening_nbv"
        ),
        CheckConstraint(
            "accumulated_depreciation >= 0", name="ck_fixed_asset_schedule_accumulated"
        ),
        CheckConstraint(
            "closing_net_book_value >= 0", name="ck_fixed_asset_schedule_closing_nbv"
        ),
        CheckConstraint(
            "status IN ('PLANNED', 'POSTED', 'VOIDED')",
            name="ck_fixed_asset_schedule_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        String,
        ForeignKey("fixed_asset_depreciation_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_period_id = Column(
        String,
        ForeignKey("fiscal_periods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    sequence_number = Column(Integer, nullable=False)
    scheduled_date = Column(Date, nullable=False, index=True)
    opening_net_book_value = Column(Numeric(18, 2), nullable=False)
    depreciation_amount = Column(Numeric(18, 2), nullable=False)
    accumulated_depreciation = Column(Numeric(18, 2), nullable=False)
    closing_net_book_value = Column(Numeric(18, 2), nullable=False)
    status = Column(String(32), nullable=False, default="PLANNED", index=True)
    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    posted_at = Column(DateTime, nullable=True)
    posted_by_user_id = Column(String, nullable=True)

    plan = relationship("DepreciationPlan", back_populates="schedule_lines")
