"""Add bank transactions and auditable reconciliations.

Revision ID: 0003_add_bank_reconciliation
Revises: 0002_add_period_closings
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_bank_reconciliation"
down_revision: str | None = "0002_add_period_closings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("bank_account_id", sa.String(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount <> 0", name="ck_bank_transaction_non_zero_amount"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "external_id",
            name="uq_bank_transaction_organization_account_external",
        ),
    )
    op.create_index(
        "ix_bank_transactions_bank_account_id", "bank_transactions", ["bank_account_id"]
    )
    op.create_index(
        "ix_bank_transactions_organization_id", "bank_transactions", ["organization_id"]
    )
    op.create_index(
        "ix_bank_transactions_transaction_date",
        "bank_transactions",
        ["transaction_date"],
    )

    op.create_table(
        "bank_reconciliations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("bank_transaction_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("reconciled_by_user_id", sa.String(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "matched_amount > 0", name="ck_bank_reconciliation_positive_amount"
        ),
        sa.ForeignKeyConstraint(
            ["bank_transaction_id"], ["bank_transactions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reconciled_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bank_transaction_id", name="uq_bank_reconciliation_transaction"
        ),
        sa.UniqueConstraint("journal_entry_id", name="uq_bank_reconciliation_entry"),
    )
    op.create_index(
        "ix_bank_reconciliations_bank_transaction_id",
        "bank_reconciliations",
        ["bank_transaction_id"],
    )
    op.create_index(
        "ix_bank_reconciliations_journal_entry_id",
        "bank_reconciliations",
        ["journal_entry_id"],
    )
    op.create_index(
        "ix_bank_reconciliations_organization_id",
        "bank_reconciliations",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_reconciliations_reconciled_by_user_id",
        "bank_reconciliations",
        ["reconciled_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_reconciliations_reconciled_by_user_id",
        table_name="bank_reconciliations",
    )
    op.drop_index(
        "ix_bank_reconciliations_organization_id", table_name="bank_reconciliations"
    )
    op.drop_index(
        "ix_bank_reconciliations_journal_entry_id", table_name="bank_reconciliations"
    )
    op.drop_index(
        "ix_bank_reconciliations_bank_transaction_id",
        table_name="bank_reconciliations",
    )
    op.drop_table("bank_reconciliations")
    op.drop_index(
        "ix_bank_transactions_transaction_date", table_name="bank_transactions"
    )
    op.drop_index(
        "ix_bank_transactions_organization_id", table_name="bank_transactions"
    )
    op.drop_index(
        "ix_bank_transactions_bank_account_id", table_name="bank_transactions"
    )
    op.drop_table("bank_transactions")
