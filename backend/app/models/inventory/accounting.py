from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class InventoryAccountingProfile(Base):
    __tablename__ = "inventory_accounting_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_inv_acc_profile_org"),
        ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_inv_acc_profile_journal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "inventory_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_inventory",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "receipt_counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_receipt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "cost_of_sales_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_cogs",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "adjustment_gain_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_gain",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "adjustment_loss_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_loss",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_id = Column(String, nullable=False)
    inventory_account_id = Column(String, nullable=False)
    receipt_counterpart_account_id = Column(String, nullable=False)
    cost_of_sales_account_id = Column(String, nullable=False)
    adjustment_gain_account_id = Column(String, nullable=False)
    adjustment_loss_account_id = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class InventoryAccountingPosting(Base):
    __tablename__ = "inventory_accounting_postings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_inv_acc_post_source",
        ),
        UniqueConstraint(
            "organization_id", "journal_entry_id", name="uq_inv_acc_post_entry"
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["stock_movements.organization_id", "stock_movements.id"],
            name="fk_inv_acc_post_movement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_inv_acc_post_entry",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_module = Column(String(64), nullable=False, default="INVENTORY")
    source_type = Column(String(64), nullable=False)
    source_id = Column(String, nullable=False, index=True)
    journal_entry_id = Column(String, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="POSTED")

    movement = relationship("StockMovement", foreign_keys=[source_id], uselist=False)
    journal_entry = relationship("JournalEntry", foreign_keys=[journal_entry_id])
