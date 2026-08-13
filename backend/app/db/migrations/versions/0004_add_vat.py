"""Add effective-dated VAT rates and journal-linked VAT entries.

Revision ID: 0004_add_vat
Revises: 0003_add_bank_reconciliation
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_vat"
down_revision: str | None = "0003_add_bank_reconciliation"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "vat_rates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("input_vat_account_id", sa.String(), nullable=True),
        sa.Column("output_vat_account_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "rate >= 0 AND rate <= 100", name="ck_vat_rate_percentage_range"
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_vat_rate_effective_dates",
        ),
        sa.ForeignKeyConstraint(
            ["input_vat_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["output_vat_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "code",
            "effective_from",
            name="uq_vat_rate_effective_code",
        ),
    )
    op.create_index("ix_vat_rates_effective_from", "vat_rates", ["effective_from"])
    op.create_index("ix_vat_rates_organization_id", "vat_rates", ["organization_id"])

    op.create_table(
        "vat_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("vat_rate_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("tax_date", sa.Date(), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "direction IN ('INPUT', 'OUTPUT')", name="ck_vat_entry_direction"
        ),
        sa.CheckConstraint(
            "taxable_amount >= 0", name="ck_vat_entry_taxable_non_negative"
        ),
        sa.CheckConstraint("vat_amount >= 0", name="ck_vat_entry_amount_non_negative"),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["vat_rate_id"], ["vat_rates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id", name="uq_vat_entry_journal_entry"),
    )
    op.create_index(
        "ix_vat_entries_journal_entry_id", "vat_entries", ["journal_entry_id"]
    )
    op.create_index(
        "ix_vat_entries_organization_id", "vat_entries", ["organization_id"]
    )
    op.create_index("ix_vat_entries_tax_date", "vat_entries", ["tax_date"])
    op.create_index("ix_vat_entries_vat_rate_id", "vat_entries", ["vat_rate_id"])


def downgrade() -> None:
    op.drop_index("ix_vat_entries_vat_rate_id", table_name="vat_entries")
    op.drop_index("ix_vat_entries_tax_date", table_name="vat_entries")
    op.drop_index("ix_vat_entries_organization_id", table_name="vat_entries")
    op.drop_index("ix_vat_entries_journal_entry_id", table_name="vat_entries")
    op.drop_table("vat_entries")
    op.drop_index("ix_vat_rates_organization_id", table_name="vat_rates")
    op.drop_index("ix_vat_rates_effective_from", table_name="vat_rates")
    op.drop_table("vat_rates")
