"""Add VAT declaration workflow.

Revision ID: 0015_vat_declarations
Revises: 0014_cash_flow_statement
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_vat_declarations"
down_revision: str | None = "0014_cash_flow_statement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def upgrade() -> None:
    op.create_table(
        "vat_declarations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total_output_vat", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_input_vat", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_vat_payable", sa.Numeric(18, 2), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('READY', 'SUBMITTED')", name="ck_vat_declaration_status"
        ),
        sa.CheckConstraint(
            "total_output_vat >= 0", name="ck_vat_declaration_output_non_negative"
        ),
        sa.CheckConstraint(
            "total_input_vat >= 0", name="ck_vat_declaration_input_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "fiscal_period_id",
            name="uq_vat_declaration_organization_period",
        ),
    )
    op.create_index(
        "ix_vat_declarations_organization_id", "vat_declarations", ["organization_id"]
    )
    op.create_index(
        "ix_vat_declarations_fiscal_period_id",
        "vat_declarations",
        ["fiscal_period_id"],
    )
    op.execute(f"ALTER TABLE vat_declarations OWNER TO {ACCOUNTING_OWNER_ROLE}")
    op.execute("REVOKE ALL ON TABLE vat_declarations FROM PUBLIC")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE vat_declarations TO {APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.drop_index("ix_vat_declarations_fiscal_period_id", table_name="vat_declarations")
    op.drop_index("ix_vat_declarations_organization_id", table_name="vat_declarations")
    op.drop_table("vat_declarations")
