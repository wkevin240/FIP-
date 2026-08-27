from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class LiquidityAlertConfiguration(Base):
    __tablename__ = "liquidity_alert_configurations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "alert_code",
            name="uq_liquidity_alert_config_org_code",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_liquidity_alert_config_org_id",
        ),
        CheckConstraint(
            "alert_code IN ('LOW_LIQUIDITY','LIQUIDITY_GAP','NEGATIVE_FORECAST','AR_COLLECTION_RISK','AP_PAYMENT_PRESSURE')",
            name="ck_liquidity_alert_config_code",
        ),
        CheckConstraint(
            "threshold_amount IS NULL OR threshold_amount >= 0",
            name="ck_liquidity_alert_config_threshold_non_negative",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_liquidity_alert_config_effective_dates",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    alert_code = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    threshold_amount = Column(Numeric(18, 2), nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    currency = Column(String(3), nullable=True)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
