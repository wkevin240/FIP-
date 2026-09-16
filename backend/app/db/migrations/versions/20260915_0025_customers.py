"""Add tenant-scoped customer master data.

Revision ID: 20260915_0025
Revises: 20260914_0024
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260915_0025"
down_revision: Union[str, None] = "20260914_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.CheckConstraint("btrim(code) <> ''", name="ck_customers_code_not_blank"),
        sa.CheckConstraint("code !~ '\\s'", name="ck_customers_code_no_whitespace"),
        sa.CheckConstraint("btrim(legal_name) <> ''", name="ck_customers_legal_name_not_blank"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_customer_organization_code"),
        sa.UniqueConstraint("organization_id", "tax_id", name="uq_customer_organization_tax_id"),
    )
    op.create_index("ix_customers_organization_id", "customers", ["organization_id"], unique=False)
    op.create_index("ix_customers_code", "customers", ["code"], unique=False)
    op.create_index("ix_customers_created_by", "customers", ["created_by"], unique=False)
    op.create_index("ix_customers_updated_by", "customers", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_customers_updated_by", table_name="customers")
    op.drop_index("ix_customers_created_by", table_name="customers")
    op.drop_index("ix_customers_code", table_name="customers")
    op.drop_index("ix_customers_organization_id", table_name="customers")
    op.drop_table("customers")
