"""Add tenant-scoped SYSCOHADA professional reporting mappings.

Revision ID: 0013_professional_reporting
Revises: 0012_accounting_hardening
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_professional_reporting"
down_revision: str | None = "0012_accounting_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def upgrade() -> None:
    op.create_table(
        "financial_statement_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("framework", sa.String(length=32), nullable=False),
        sa.Column("statement_code", sa.String(length=32), nullable=False),
        sa.Column("presentation_role", sa.String(length=32), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("section_label", sa.String(length=255), nullable=False),
        sa.Column("line_code", sa.String(length=64), nullable=False),
        sa.Column("line_label", sa.String(length=255), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "framework IN ('SYSCOHADA')", name="ck_financial_mapping_framework"
        ),
        sa.CheckConstraint(
            "statement_code IN ('BALANCE_SHEET', 'INCOME_STATEMENT')",
            name="ck_financial_mapping_statement_code",
        ),
        sa.CheckConstraint(
            "(statement_code = 'BALANCE_SHEET' AND presentation_role IN ('ASSETS', 'LIABILITIES_EQUITY')) "
            "OR (statement_code = 'INCOME_STATEMENT' AND presentation_role IN ('REVENUE', 'EXPENSE'))",
            name="ck_financial_mapping_presentation_role",
        ),
        sa.CheckConstraint(
            "line_code <> ''", name="ck_financial_mapping_line_code_not_empty"
        ),
        sa.CheckConstraint(
            "line_label <> ''", name="ck_financial_mapping_line_label_not_empty"
        ),
        sa.CheckConstraint(
            "section_code <> ''", name="ck_financial_mapping_section_code_not_empty"
        ),
        sa.CheckConstraint(
            "display_order >= 0", name="ck_financial_mapping_display_order"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_financial_mapping_organization_account",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "account_id",
            "framework",
            "statement_code",
            name="uq_financial_mapping_organization_account_statement",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "framework",
            "statement_code",
            "line_code",
            "account_id",
            name="uq_financial_mapping_organization_line_account",
        ),
    )
    op.create_index(
        "ix_financial_statement_mappings_organization_id",
        "financial_statement_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_financial_statement_mappings_account_id",
        "financial_statement_mappings",
        ["account_id"],
    )
    op.execute(
        f"ALTER TABLE financial_statement_mappings OWNER TO {ACCOUNTING_OWNER_ROLE}"
    )
    op.execute("REVOKE ALL ON TABLE financial_statement_mappings FROM PUBLIC")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE financial_statement_mappings TO {APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_statement_mappings_account_id",
        table_name="financial_statement_mappings",
    )
    op.drop_index(
        "ix_financial_statement_mappings_organization_id",
        table_name="financial_statement_mappings",
    )
    op.drop_table("financial_statement_mappings")
