"""Add treasury bank account profiles.

Revision ID: 0007_add_treasury_bank_accounts
Revises: 0006_add_invoicing
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_treasury_bank_accounts"
down_revision: str | None = "0006_add_invoicing"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "treasury_bank_accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("ledger_account_id", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(length=128), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_number", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("opening_balance", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ledger_account_id"], ["accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_number",
            name="uq_treasury_bank_account_number",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "ledger_account_id",
            name="uq_treasury_bank_account_ledger",
        ),
    )
    op.create_index(
        "ix_treasury_bank_accounts_ledger_account_id",
        "treasury_bank_accounts",
        ["ledger_account_id"],
    )
    op.create_index(
        "ix_treasury_bank_accounts_opening_date",
        "treasury_bank_accounts",
        ["opening_date"],
    )
    op.create_index(
        "ix_treasury_bank_accounts_organization_id",
        "treasury_bank_accounts",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_treasury_bank_accounts_organization_id",
        table_name="treasury_bank_accounts",
    )
    op.drop_index(
        "ix_treasury_bank_accounts_opening_date",
        table_name="treasury_bank_accounts",
    )
    op.drop_index(
        "ix_treasury_bank_accounts_ledger_account_id",
        table_name="treasury_bank_accounts",
    )
    op.drop_table("treasury_bank_accounts")
