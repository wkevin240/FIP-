"""Add explicit bank recognition rules and accounting proposals.

Revision ID: 0022_bank_rules_accounting
Revises: 0021_bank_statement_imports
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_bank_rules_accounting"
down_revision: str | None = "0021_bank_statement_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure_rules() -> None:
    op.execute("ALTER TABLE public.bank_accounting_rules OWNER TO fip_accounting_owner")
    op.execute("REVOKE ALL ON TABLE public.bank_accounting_rules FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.bank_accounting_rules TO fip_user"
    )


def _secure_proposals() -> None:
    op.execute(
        "ALTER TABLE public.bank_transaction_accounting_proposals "
        "OWNER TO fip_accounting_owner"
    )
    op.execute(
        "REVOKE ALL ON TABLE public.bank_transaction_accounting_proposals FROM PUBLIC"
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE public.bank_transaction_accounting_proposals "
        "TO fip_user"
    )
    op.execute(
        "GRANT UPDATE (status, journal_entry_id, decision_idempotency_key, "
        "rejection_reason, decided_by_user_id, decided_at, updated_at) "
        "ON TABLE public.bank_transaction_accounting_proposals TO fip_user"
    )


def upgrade() -> None:
    op.create_table(
        "bank_accounting_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description_pattern", sa.String(length=256), nullable=True),
        sa.Column("reference_pattern", sa.String(length=256), nullable=True),
        sa.Column("amount_min", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount_max", sa.Numeric(18, 2), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=True),
        sa.Column("counterpart_account_id", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("priority >= 0", name="ck_bank_accounting_rule_priority"),
        sa.CheckConstraint(
            "amount_min IS NULL OR amount_min >= 0",
            name="ck_bank_accounting_rule_min_non_negative",
        ),
        sa.CheckConstraint(
            "amount_max IS NULL OR amount_max >= 0",
            name="ck_bank_accounting_rule_max_non_negative",
        ),
        sa.CheckConstraint(
            "amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max",
            name="ck_bank_accounting_rule_amount_bounds",
        ),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('CREDIT', 'DEBIT')",
            name="ck_bank_accounting_rule_direction",
        ),
        sa.CheckConstraint(
            "description_pattern IS NOT NULL OR reference_pattern IS NOT NULL "
            "OR amount_min IS NOT NULL OR amount_max IS NOT NULL OR direction IS NOT NULL",
            name="ck_bank_accounting_rule_has_criterion",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_accounting_rules_organization_counterpart",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_bank_accounting_rules_organization_id_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "name", name="uq_bank_accounting_rules_organization_name"
        ),
    )
    _secure_rules()
    op.create_index(
        "ix_bank_accounting_rules_organization_id",
        "bank_accounting_rules",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_accounting_rules_counterpart_account_id",
        "bank_accounting_rules",
        ["counterpart_account_id"],
    )
    op.create_index(
        "ix_bank_accounting_rules_active_priority",
        "bank_accounting_rules",
        ["organization_id", "is_active", "priority"],
    )

    op.create_table(
        "bank_transaction_accounting_proposals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("bank_transaction_id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("counterpart_account_id", sa.String(), nullable=False),
        sa.Column("rule_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("rule_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=True),
        sa.Column("decision_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("decided_by_user_id", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'VALIDATED', 'REJECTED')",
            name="ck_bank_accounting_proposal_status",
        ),
        sa.CheckConstraint(
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
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_accounting_proposals_organization_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "rule_id"],
            ["bank_accounting_rules.organization_id", "bank_accounting_rules.id"],
            name="fk_bank_accounting_proposals_organization_rule",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_accounting_proposals_organization_counterpart",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_bank_accounting_proposals_organization_entry",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_bank_accounting_proposals_organization_id_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "bank_transaction_id",
            "rule_snapshot_hash",
            name="uq_bank_accounting_proposals_transaction_snapshot",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "decision_idempotency_key",
            name="uq_bank_accounting_proposals_decision_idempotency",
        ),
        sa.UniqueConstraint(
            "journal_entry_id", name="uq_bank_accounting_proposals_entry"
        ),
    )
    _secure_proposals()
    op.create_index(
        "ix_bank_accounting_proposals_organization_id",
        "bank_transaction_accounting_proposals",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_accounting_proposals_bank_transaction_id",
        "bank_transaction_accounting_proposals",
        ["bank_transaction_id"],
    )
    op.create_index(
        "ix_bank_accounting_proposals_rule_id",
        "bank_transaction_accounting_proposals",
        ["rule_id"],
    )
    op.create_index(
        "ix_bank_accounting_proposals_status",
        "bank_transaction_accounting_proposals",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_accounting_proposals_status",
        table_name="bank_transaction_accounting_proposals",
    )
    op.drop_index(
        "ix_bank_accounting_proposals_rule_id",
        table_name="bank_transaction_accounting_proposals",
    )
    op.drop_index(
        "ix_bank_accounting_proposals_bank_transaction_id",
        table_name="bank_transaction_accounting_proposals",
    )
    op.drop_index(
        "ix_bank_accounting_proposals_organization_id",
        table_name="bank_transaction_accounting_proposals",
    )
    op.drop_table("bank_transaction_accounting_proposals")
    op.drop_index(
        "ix_bank_accounting_rules_active_priority",
        table_name="bank_accounting_rules",
    )
    op.drop_index(
        "ix_bank_accounting_rules_counterpart_account_id",
        table_name="bank_accounting_rules",
    )
    op.drop_index(
        "ix_bank_accounting_rules_organization_id",
        table_name="bank_accounting_rules",
    )
    op.drop_table("bank_accounting_rules")
