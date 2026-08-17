from sqlalchemy import (
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class TreasuryAccountingProfile(Base):
    __tablename__ = "treasury_accounting_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_treasury_acc_profile_org"),
        ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_treasury_acc_profile_journal",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    journal_id = Column(String, nullable=False)


class TreasuryAccountingPosting(Base):
    __tablename__ = "treasury_accounting_postings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_treasury_acc_post_source",
        ),
        UniqueConstraint(
            "organization_id", "journal_entry_id", name="uq_treasury_acc_post_entry"
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_treasury_acc_post_transaction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_treasury_acc_post_counterpart",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_treasury_acc_post_entry",
            ondelete="RESTRICT",
        ),
    )
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    source_module = Column(String(64), nullable=False, default="TREASURY")
    source_type = Column(String(64), nullable=False, default="BANK_TRANSACTION")
    source_id = Column(String, nullable=False)
    journal_entry_id = Column(String, nullable=False)
    counterpart_account_id = Column(String, nullable=False)
    status = Column(String(16), nullable=False, default="POSTED")
