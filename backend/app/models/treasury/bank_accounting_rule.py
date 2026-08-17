from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class BankAccountingRule(Base):
    """Explicit tenant-owned recognition rule for imported bank transactions.

    A rule deliberately has no implicit counterpart account or catch-all default:
    at least one matching criterion and one configured counterpart account are required.
    Lower numeric priorities take precedence. Ties are intentionally surfaced as
    ambiguous by the service instead of choosing an arbitrary accounting outcome.
    """

    __tablename__ = "bank_accounting_rules"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_bank_accounting_rule_priority"),
        CheckConstraint(
            "amount_min IS NULL OR amount_min >= 0",
            name="ck_bank_accounting_rule_min_non_negative",
        ),
        CheckConstraint(
            "amount_max IS NULL OR amount_max >= 0",
            name="ck_bank_accounting_rule_max_non_negative",
        ),
        CheckConstraint(
            "amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max",
            name="ck_bank_accounting_rule_amount_bounds",
        ),
        CheckConstraint(
            "direction IS NULL OR direction IN ('CREDIT', 'DEBIT')",
            name="ck_bank_accounting_rule_direction",
        ),
        CheckConstraint(
            "description_pattern IS NOT NULL OR reference_pattern IS NOT NULL "
            "OR amount_min IS NOT NULL OR amount_max IS NOT NULL OR direction IS NOT NULL",
            name="ck_bank_accounting_rule_has_criterion",
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_bank_accounting_rules_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id", "name", name="uq_bank_accounting_rules_organization_name"
        ),
        ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_accounting_rules_organization_counterpart",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    description_pattern = Column(String(256), nullable=True)
    reference_pattern = Column(String(256), nullable=True)
    amount_min = Column(Numeric(18, 2), nullable=True)
    amount_max = Column(Numeric(18, 2), nullable=True)
    direction = Column(String(16), nullable=True)
    counterpart_account_id = Column(String, nullable=False, index=True)
    priority = Column(Integer, nullable=False)
    category = Column(String(64), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class BankTransactionAccountingProposal(Base):
    """A non-posting accounting proposal generated from an explicit bank rule."""

    __tablename__ = "bank_transaction_accounting_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'VALIDATED', 'REJECTED')",
            name="ck_bank_accounting_proposal_status",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND journal_entry_id IS NULL "
            "AND decided_by_user_id IS NULL AND decided_at IS NULL "
            "AND decision_idempotency_key IS NULL AND rejection_reason IS NULL) "
            "OR (status = 'VALIDATED' AND journal_entry_id IS NOT NULL "
            "AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND decision_idempotency_key IS NOT NULL AND rejection_reason IS NULL) "
            "OR (status = 'REJECTED' AND journal_entry_id IS NULL "
            "AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND decision_idempotency_key IS NOT NULL AND rejection_reason IS NOT NULL)",
            name="ck_bank_accounting_proposal_decision_state",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_bank_accounting_proposals_organization_id_id",
        ),
        UniqueConstraint(
            "organization_id",
            "bank_transaction_id",
            "rule_snapshot_hash",
            name="uq_bank_accounting_proposals_transaction_snapshot",
        ),
        UniqueConstraint(
            "organization_id",
            "decision_idempotency_key",
            name="uq_bank_accounting_proposals_decision_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_accounting_proposals_organization_transaction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "rule_id"],
            ["bank_accounting_rules.organization_id", "bank_accounting_rules.id"],
            name="fk_bank_accounting_proposals_organization_rule",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_accounting_proposals_organization_counterpart",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_bank_accounting_proposals_organization_entry",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_transaction_id = Column(String, nullable=False, index=True)
    rule_id = Column(String, nullable=False, index=True)
    counterpart_account_id = Column(String, nullable=False)
    rule_name = Column(String(120), nullable=False)
    category = Column(String(64), nullable=True)
    rule_snapshot_hash = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    journal_entry_id = Column(String, nullable=True, unique=True)
    decision_idempotency_key = Column(String(128), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    decided_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at = Column(DateTime(timezone=True), nullable=True)
