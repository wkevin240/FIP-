"""Add banking control center exceptions and statement closures.

Revision ID: 0024_banking_control
Revises: 0023_procurement_invoices
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_banking_control"
down_revision: str | None = "0023_procurement_invoices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str) -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "banking_control_exceptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("bank_transaction_id", sa.String(), nullable=False),
        sa.Column("statement_import_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_banking_control_exception_org_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_banking_control_exception_org_import",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "bank_transaction_id",
            name="uq_banking_control_exception_org_transaction",
        ),
        sa.CheckConstraint(
            "status IN ('NO_MATCH', 'AMBIGUOUS', 'PENDING', 'REJECTED', 'INVALID_RULE', 'POSTED_UNRECONCILED', 'RECONCILED')",
            name="ck_banking_control_exception_status",
        ),
    )
    _secure("banking_control_exceptions")
    op.create_table(
        "bank_statement_closures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("statement_import_id", sa.String(), nullable=False),
        sa.Column(
            "closed_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("reconciled_count", sa.Integer(), nullable=False),
        sa.Column("unresolved_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_bank_statement_closure_org_import",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "statement_import_id",
            name="uq_bank_statement_closure_org_import",
        ),
        sa.CheckConstraint(
            "unresolved_count = 0", name="ck_bank_statement_closure_no_unresolved"
        ),
        sa.CheckConstraint(
            "imported_count >= 0 AND reconciled_count >= 0",
            name="ck_bank_statement_closure_counts_non_negative",
        ),
        sa.CheckConstraint(
            "reconciled_count <= imported_count",
            name="ck_bank_statement_closure_reconciled_bound",
        ),
    )
    _secure("bank_statement_closures")


def downgrade() -> None:
    op.drop_table("bank_statement_closures")
    op.drop_table("banking_control_exceptions")
