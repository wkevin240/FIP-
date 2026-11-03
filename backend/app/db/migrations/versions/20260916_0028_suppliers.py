"""Add tenant-scoped supplier master data.

Revision ID: 20260916_0028
Revises: 20260915_0027
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260916_0028"
down_revision: Union[str, None] = "20260915_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
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
        sa.CheckConstraint("btrim(code) <> ''", name="ck_suppliers_code_not_blank"),
        sa.CheckConstraint("code !~ '\\s'", name="ck_suppliers_code_no_whitespace"),
        sa.CheckConstraint("btrim(code) = code AND code = upper(code)", name="ck_suppliers_code_canonical"),
        sa.CheckConstraint("btrim(legal_name) <> ''", name="ck_suppliers_legal_name_not_blank"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_supplier_organization_code"),
        sa.UniqueConstraint("organization_id", "tax_id", name="uq_supplier_organization_tax_id"),
    )
    op.create_index("ix_suppliers_organization_id", "suppliers", ["organization_id"], unique=False)
    op.create_index("ix_suppliers_code", "suppliers", ["code"], unique=False)
    op.create_index("ix_suppliers_created_by", "suppliers", ["created_by"], unique=False)
    op.create_index("ix_suppliers_updated_by", "suppliers", ["updated_by"], unique=False)
    op.create_index(
        "ix_suppliers_organization_active_code",
        "suppliers",
        ["organization_id", "is_active", "code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_suppliers_organization_active_code", table_name="suppliers")
    op.drop_index("ix_suppliers_updated_by", table_name="suppliers")
    op.drop_index("ix_suppliers_created_by", table_name="suppliers")
    op.drop_index("ix_suppliers_code", table_name="suppliers")
    op.drop_index("ix_suppliers_organization_id", table_name="suppliers")
    op.drop_table("suppliers")
