"""Add immutable accounting period closings.

Revision ID: 0002_add_period_closings
Revises: 0001_initial_schema
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_period_closings"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "period_closings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("closed_by_user_id", sa.String(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_entry_count", sa.Integer(), nullable=False),
        sa.Column("posted_line_count", sa.Integer(), nullable=False),
        sa.Column("total_debit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_credit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("control_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "posted_entry_count >= 0", name="ck_period_closing_entry_count_non_negative"
        ),
        sa.CheckConstraint(
            "posted_line_count >= 0", name="ck_period_closing_line_count_non_negative"
        ),
        sa.CheckConstraint(
            "total_debit >= 0", name="ck_period_closing_total_debit_non_negative"
        ),
        sa.CheckConstraint(
            "total_credit >= 0", name="ck_period_closing_total_credit_non_negative"
        ),
        sa.CheckConstraint(
            "total_debit = total_credit", name="ck_period_closing_totals_balance"
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_period_id", name="uq_period_closing_fiscal_period"),
    )
    op.create_index(
        "ix_period_closings_closed_by_user_id", "period_closings", ["closed_by_user_id"]
    )
    op.create_index(
        "ix_period_closings_fiscal_period_id", "period_closings", ["fiscal_period_id"]
    )
    op.create_index(
        "ix_period_closings_organization_id", "period_closings", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_period_closings_organization_id", table_name="period_closings")
    op.drop_index("ix_period_closings_fiscal_period_id", table_name="period_closings")
    op.drop_index("ix_period_closings_closed_by_user_id", table_name="period_closings")
    op.drop_table("period_closings")
