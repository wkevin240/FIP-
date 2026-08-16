"""Add inventory to Accounting posting.

Revision ID: 0017_inventory_accounting_posting
Revises: 0016_invoice_accounting_posting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_inventory_accounting"
down_revision: str | None = "0016_invoice_accounting_posting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "fip_user"
OWNER_ROLE = "fip_accounting_owner"


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE {table} OWNER TO {OWNER_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {APP_ROLE}")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_stock_movements_organization_id_id",
        "stock_movements",
        ["organization_id", "id"],
    )
    op.create_table(
        "inventory_accounting_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("inventory_account_id", sa.String(), nullable=False),
        sa.Column("receipt_counterpart_account_id", sa.String(), nullable=False),
        sa.Column("cost_of_sales_account_id", sa.String(), nullable=False),
        sa.Column("adjustment_gain_account_id", sa.String(), nullable=False),
        sa.Column("adjustment_loss_account_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_inv_acc_profile_journal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "inventory_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_inventory",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "receipt_counterpart_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_receipt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "cost_of_sales_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_cogs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "adjustment_gain_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_gain",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "adjustment_loss_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_loss",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_inv_acc_profile_org"),
    )
    op.create_index(
        "ix_inventory_accounting_profiles_organization_id",
        "inventory_accounting_profiles",
        ["organization_id"],
    )
    _secure("inventory_accounting_profiles")
    op.create_table(
        "inventory_accounting_postings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("source_module", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["stock_movements.organization_id", "stock_movements.id"],
            name="fk_inv_acc_post_movement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_inv_acc_post_entry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_inv_acc_post_source",
        ),
        sa.UniqueConstraint(
            "organization_id", "journal_entry_id", name="uq_inv_acc_post_entry"
        ),
    )
    op.create_index(
        "ix_inventory_accounting_postings_organization_id",
        "inventory_accounting_postings",
        ["organization_id"],
    )
    op.create_index(
        "ix_inventory_accounting_postings_source_id",
        "inventory_accounting_postings",
        ["source_id"],
    )
    _secure("inventory_accounting_postings")


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_accounting_postings_source_id",
        table_name="inventory_accounting_postings",
    )
    op.drop_index(
        "ix_inventory_accounting_postings_organization_id",
        table_name="inventory_accounting_postings",
    )
    op.drop_table("inventory_accounting_postings")
    op.drop_index(
        "ix_inventory_accounting_profiles_organization_id",
        table_name="inventory_accounting_profiles",
    )
    op.drop_table("inventory_accounting_profiles")
    op.drop_constraint(
        "uq_stock_movements_organization_id_id", "stock_movements", type_="unique"
    )
