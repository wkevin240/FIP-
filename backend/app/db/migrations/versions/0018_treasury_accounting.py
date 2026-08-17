"""Add treasury accounting posting.

Revision ID: 0018_treasury_accounting
Revises: 0017_inventory_accounting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_treasury_accounting"
down_revision: str | None = "0017_inventory_accounting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE {table} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO fip_user")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_bank_transactions_organization_id_id",
        "bank_transactions",
        ["organization_id", "id"],
    )
    op.create_table(
        "treasury_accounting_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_treasury_acc_profile_journal",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_treasury_acc_profile_org"),
    )
    _secure("treasury_accounting_profiles")
    op.create_table(
        "treasury_accounting_postings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("source_module", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("counterpart_account_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_treasury_acc_post_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_treasury_acc_post_counterpart",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_treasury_acc_post_entry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_treasury_acc_post_source",
        ),
        sa.UniqueConstraint(
            "organization_id", "journal_entry_id", name="uq_treasury_acc_post_entry"
        ),
    )
    _secure("treasury_accounting_postings")


def downgrade() -> None:
    op.drop_table("treasury_accounting_postings")
    op.drop_table("treasury_accounting_profiles")
    op.drop_constraint(
        "uq_bank_transactions_organization_id_id", "bank_transactions", type_="unique"
    )
