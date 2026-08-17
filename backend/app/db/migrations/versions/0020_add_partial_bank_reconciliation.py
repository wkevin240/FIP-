"""Add partial and grouped bank reconciliation allocations.

Revision ID: 0020_partial_bank_reconciliation
Revises: 0019_invoice_settlement
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_partial_bank_reconciliation"
down_revision: str | None = "0019_invoice_settlement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT ON TABLE public.{table} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "bank_reconciliation_batches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("bank_account_id", sa.String(), nullable=False),
        sa.Column("reconciled_by_user_id", sa.String(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("allocated_total", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "bank_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_bank_reconciliation_batches_org_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reconciled_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_bank_reconciliation_batches_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_bank_reconciliation_batches_idempotency",
        ),
        sa.CheckConstraint(
            "allocated_total > 0",
            name="ck_bank_reconciliation_batches_positive_total",
        ),
    )
    _secure("bank_reconciliation_batches")
    op.create_index(
        "ix_bank_reconciliation_batches_organization_id",
        "bank_reconciliation_batches",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_reconciliation_batches_bank_account_id",
        "bank_reconciliation_batches",
        ["bank_account_id"],
    )

    op.create_table(
        "bank_reconciliation_allocations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("bank_transaction_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("matched_amount", sa.Numeric(18, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "batch_id"],
            [
                "bank_reconciliation_batches.organization_id",
                "bank_reconciliation_batches.id",
            ],
            name="fk_bank_reconciliation_allocations_org_batch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_reconciliation_allocations_org_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_bank_reconciliation_allocations_org_entry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "batch_id",
            "bank_transaction_id",
            "journal_entry_id",
            name="uq_bank_reconciliation_allocation_batch_pair",
        ),
        sa.CheckConstraint(
            "matched_amount > 0",
            name="ck_bank_reconciliation_allocations_positive_amount",
        ),
    )
    _secure("bank_reconciliation_allocations")
    op.create_index(
        "ix_bank_reconciliation_allocations_transaction",
        "bank_reconciliation_allocations",
        ["organization_id", "bank_transaction_id"],
    )
    op.create_index(
        "ix_bank_reconciliation_allocations_entry",
        "bank_reconciliation_allocations",
        ["organization_id", "journal_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_reconciliation_allocations_entry",
        table_name="bank_reconciliation_allocations",
    )
    op.drop_index(
        "ix_bank_reconciliation_allocations_transaction",
        table_name="bank_reconciliation_allocations",
    )
    op.drop_table("bank_reconciliation_allocations")
    op.drop_index(
        "ix_bank_reconciliation_batches_bank_account_id",
        table_name="bank_reconciliation_batches",
    )
    op.drop_index(
        "ix_bank_reconciliation_batches_organization_id",
        table_name="bank_reconciliation_batches",
    )
    op.drop_table("bank_reconciliation_batches")
