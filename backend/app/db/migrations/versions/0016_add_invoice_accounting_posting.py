"""Add transactional invoicing to Accounting posting.

Revision ID: 0016_invoice_accounting_posting
Revises: 0015_vat_declarations
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_invoice_accounting_posting"
down_revision: str | None = "0015_vat_declarations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def _secure_table(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} OWNER TO {ACCOUNTING_OWNER_ROLE}")
    op.execute(f"REVOKE ALL ON TABLE {table_name} FROM PUBLIC")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table_name} TO {APPLICATION_ROLE}"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_invoices_organization_id_id", "invoices", ["organization_id", "id"]
    )
    op.create_table(
        "invoice_accounting_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("receivable_account_id", sa.String(), nullable=False),
        sa.Column("revenue_account_id", sa.String(), nullable=False),
        sa.Column("collected_vat_account_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_inv_acc_profile_org_journal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "receivable_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_receivable",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "revenue_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_revenue",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "collected_vat_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_inv_acc_profile_org_collected_vat",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            name="uq_invoice_accounting_profile_organization",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_invoice_accounting_profiles_organization_id_id",
        ),
    )
    op.create_index(
        "ix_invoice_accounting_profiles_organization_id",
        "invoice_accounting_profiles",
        ["organization_id"],
    )
    _secure_table("invoice_accounting_profiles")

    op.create_table(
        "invoice_accounting_postings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("source_module", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "source_module = 'INVOICING'",
            name="ck_invoice_accounting_posting_source_module",
        ),
        sa.CheckConstraint(
            "source_type = 'INVOICE'",
            name="ck_invoice_accounting_posting_source_type",
        ),
        sa.CheckConstraint(
            "status = 'POSTED'", name="ck_invoice_accounting_posting_status"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_inv_acc_post_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name="fk_inv_acc_post_org_journal_entry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_module",
            "source_type",
            "source_id",
            name="uq_invoice_accounting_posting_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_invoice_accounting_posting_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "journal_entry_id",
            name="uq_invoice_accounting_posting_journal_entry",
        ),
    )
    op.create_index(
        "ix_invoice_accounting_postings_organization_id",
        "invoice_accounting_postings",
        ["organization_id"],
    )
    op.create_index(
        "ix_invoice_accounting_postings_source_id",
        "invoice_accounting_postings",
        ["source_id"],
    )
    op.create_index(
        "ix_invoice_accounting_postings_journal_entry_id",
        "invoice_accounting_postings",
        ["journal_entry_id"],
    )
    _secure_table("invoice_accounting_postings")


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_accounting_postings_journal_entry_id",
        table_name="invoice_accounting_postings",
    )
    op.drop_index(
        "ix_invoice_accounting_postings_source_id",
        table_name="invoice_accounting_postings",
    )
    op.drop_index(
        "ix_invoice_accounting_postings_organization_id",
        table_name="invoice_accounting_postings",
    )
    op.drop_table("invoice_accounting_postings")
    op.drop_index(
        "ix_invoice_accounting_profiles_organization_id",
        table_name="invoice_accounting_profiles",
    )
    op.drop_table("invoice_accounting_profiles")
    op.drop_constraint("uq_invoices_organization_id_id", "invoices", type_="unique")
