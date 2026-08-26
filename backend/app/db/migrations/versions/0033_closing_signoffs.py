"""Add auditable financial closing sign-offs.

Revision ID: 0033_closing_signoffs
Revises: 0032_profitability_mappings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_closing_signoffs"
down_revision: str | None = "0032_profitability_mappings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "closing_signoffs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("fiscal_year_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("signed_by_user_id", sa.String(), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("control_hash", sa.String(length=64), nullable=False),
        sa.Column("control_snapshot", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_closing_signoff_organization_year",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "fiscal_year_id",
            name="uq_closing_signoff_organization_year",
        ),
        sa.CheckConstraint(
            "status IN ('SIGNED', 'REVOKED')", name="ck_closing_signoff_status"
        ),
    )
    op.create_index(
        "ix_closing_signoffs_organization_id",
        "closing_signoffs",
        ["organization_id"],
    )
    op.create_index(
        "ix_closing_signoffs_fiscal_year_id", "closing_signoffs", ["fiscal_year_id"]
    )
    op.execute("ALTER TABLE public.closing_signoffs OWNER TO fip_accounting_owner")
    op.execute("REVOKE ALL ON TABLE public.closing_signoffs FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.closing_signoffs TO fip_user"
    )


def downgrade() -> None:
    op.drop_index("ix_closing_signoffs_fiscal_year_id", table_name="closing_signoffs")
    op.drop_index("ix_closing_signoffs_organization_id", table_name="closing_signoffs")
    op.drop_table("closing_signoffs")
