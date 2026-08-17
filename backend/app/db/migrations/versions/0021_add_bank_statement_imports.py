"""Add normalized idempotent bank statement imports.

Revision ID: 0021_bank_statement_imports
Revises: 0020_partial_bank_reconciliation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_bank_statement_imports"
down_revision: str | None = "0020_partial_bank_reconciliation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT ON TABLE public.{table} TO fip_user")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_treasury_bank_accounts_organization_id_id",
        "treasury_bank_accounts",
        ["organization_id", "id"],
    )
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("treasury_bank_account_id", sa.String(), nullable=False),
        sa.Column("imported_by_user_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("format_version", sa.String(length=32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "treasury_bank_account_id"],
            ["treasury_bank_accounts.organization_id", "treasury_bank_accounts.id"],
            name="fk_bank_statement_imports_org_treasury_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_bank_statement_imports_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_bank_statement_imports_idempotency",
        ),
        sa.CheckConstraint(
            "row_count > 0", name="ck_bank_statement_imports_positive_rows"
        ),
        sa.CheckConstraint(
            "imported_count >= 0 AND duplicate_count >= 0",
            name="ck_bank_statement_imports_non_negative_counts",
        ),
        sa.CheckConstraint(
            "imported_count + duplicate_count = row_count",
            name="ck_bank_statement_imports_count_reconciliation",
        ),
    )
    _secure("bank_statement_imports")
    op.create_index(
        "ix_bank_statement_imports_organization_id",
        "bank_statement_imports",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_statement_imports_treasury_bank_account_id",
        "bank_statement_imports",
        ["treasury_bank_account_id"],
    )

    op.create_table(
        "bank_statement_import_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("statement_import_id", sa.String(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("bank_transaction_id", sa.String(), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_bank_statement_import_lines_org_import",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_statement_import_lines_org_transaction",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "statement_import_id",
            "line_number",
            name="uq_bank_statement_import_lines_number",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "statement_import_id",
            "external_id",
            name="uq_bank_statement_import_lines_external",
        ),
        sa.CheckConstraint(
            "status IN ('IMPORTED', 'DUPLICATE')",
            name="ck_bank_statement_import_lines_status",
        ),
    )
    _secure("bank_statement_import_lines")
    op.create_index(
        "ix_bank_statement_import_lines_transaction",
        "bank_statement_import_lines",
        ["organization_id", "bank_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_statement_import_lines_transaction",
        table_name="bank_statement_import_lines",
    )
    op.drop_table("bank_statement_import_lines")
    op.drop_index(
        "ix_bank_statement_imports_treasury_bank_account_id",
        table_name="bank_statement_imports",
    )
    op.drop_index(
        "ix_bank_statement_imports_organization_id",
        table_name="bank_statement_imports",
    )
    op.drop_table("bank_statement_imports")
    op.drop_constraint(
        "uq_treasury_bank_accounts_organization_id_id",
        "treasury_bank_accounts",
        type_="unique",
    )
