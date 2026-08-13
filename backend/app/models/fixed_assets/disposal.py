from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class FixedAssetDisposal(Base):
    __tablename__ = "fixed_asset_disposals"
    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_fixed_asset_disposal_asset"),
        UniqueConstraint(
            "journal_entry_id", name="uq_fixed_asset_disposal_journal_entry"
        ),
        CheckConstraint("proceeds >= 0", name="ck_fixed_asset_disposal_proceeds"),
        CheckConstraint("asset_cost >= 0", name="ck_fixed_asset_disposal_asset_cost"),
        CheckConstraint(
            "accumulated_depreciation >= 0",
            name="ck_fixed_asset_disposal_accumulated_depreciation",
        ),
        CheckConstraint(
            "net_book_value >= 0", name="ck_fixed_asset_disposal_net_book_value"
        ),
        CheckConstraint("gain_amount >= 0", name="ck_fixed_asset_disposal_gain"),
        CheckConstraint("loss_amount >= 0", name="ck_fixed_asset_disposal_loss"),
        CheckConstraint(
            "status IN ('DRAFT', 'POSTED')", name="ck_fixed_asset_disposal_status"
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
    disposal_date = Column(Date, nullable=False, index=True)
    disposal_type = Column(String(32), nullable=False, default="SALE")
    proceeds = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    asset_cost = Column(Numeric(18, 2), nullable=False)
    accumulated_depreciation = Column(Numeric(18, 2), nullable=False)
    net_book_value = Column(Numeric(18, 2), nullable=False)
    gain_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    loss_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    journal_entry_id = Column(
        String,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    posted_at = Column(DateTime, nullable=True)
    posted_by_user_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    asset = relationship("FixedAsset", back_populates="disposals")


class FixedAssetAuditEvent(Base):
    __tablename__ = "fixed_asset_audit_events"
    __table_args__ = (
        CheckConstraint("action <> ''", name="ck_fixed_asset_audit_event_action"),
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
        nullable=True,
        index=True,
    )
    actor_user_id = Column(String, nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String, nullable=False, index=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(String(1000), nullable=True)
    context_ip = Column(String(64), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
