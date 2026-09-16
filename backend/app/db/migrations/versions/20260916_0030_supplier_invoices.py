"""Add tenant-scoped supplier invoice intake.

Revision ID: 20260916_0030
Revises: 20260916_0029
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260916_0030"
down_revision: Union[str, None] = "20260916_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("DRAFT", "APPROVED", "CANCELLED", name="supplierinvoicestatus"), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.CheckConstraint("btrim(invoice_number) <> ''", name="ck_supplier_invoice_number_not_blank"),
        sa.CheckConstraint("invoice_date <= due_date", name="ck_supplier_invoice_due_on_or_after_invoice"),
        sa.CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0", name="ck_supplier_invoice_amounts_non_negative"),
        sa.CheckConstraint("total_amount = subtotal + tax_amount", name="ck_supplier_invoice_total_matches_components"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_supplier_invoice_supplier_same_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "supplier_id", "invoice_number", name="uq_supplier_invoice_org_supplier_number"),
    )
    op.create_index("ix_supplier_invoices_organization_id", "supplier_invoices", ["organization_id"], unique=False)
    op.create_index("ix_supplier_invoices_supplier_id", "supplier_invoices", ["supplier_id"], unique=False)
    op.create_index("ix_supplier_invoices_invoice_date", "supplier_invoices", ["invoice_date"], unique=False)
    op.create_index("ix_supplier_invoices_due_date", "supplier_invoices", ["due_date"], unique=False)
    op.create_index("ix_supplier_invoices_status", "supplier_invoices", ["status"], unique=False)
    op.create_index("ix_supplier_invoices_created_by", "supplier_invoices", ["created_by"], unique=False)
    op.create_index("ix_supplier_invoices_updated_by", "supplier_invoices", ["updated_by"], unique=False)
    op.create_index("ix_supplier_invoices_approved_by", "supplier_invoices", ["approved_by"], unique=False)
    op.create_index(
        "ix_supplier_invoices_organization_status_date",
        "supplier_invoices",
        ["organization_id", "status", "invoice_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_invoices_organization_status_date", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_approved_by", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_updated_by", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_created_by", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_status", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_due_date", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_invoice_date", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_supplier_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_organization_id", table_name="supplier_invoices")
    op.drop_table("supplier_invoices")
    op.execute("DROP TYPE IF EXISTS supplierinvoicestatus")
