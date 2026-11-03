"""Add tenant-scoped customer invoice intake and issue lifecycle.

Revision ID: 20260923_0028
Revises: 20260915_0027
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_0028"
down_revision: Union[str, None] = "20260915_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_customers_organization_id_id",
        "customers",
        ["organization_id", "id"],
    )
    op.create_table(
        "customer_invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.CheckConstraint("btrim(invoice_number) <> ''", name="ck_customer_invoices_number_not_blank"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="ck_customer_invoices_currency_canonical"),
        sa.CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount > 0", name="ck_customer_invoices_amounts_nonnegative"),
        sa.CheckConstraint("subtotal + tax_amount = total_amount", name="ck_customer_invoices_total_matches_components"),
        sa.CheckConstraint("due_date >= invoice_date", name="ck_customer_invoices_due_date"),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND issued_by IS NULL AND issued_at IS NULL) OR "
            "(status = 'ISSUED' AND issued_by IS NOT NULL AND issued_at IS NOT NULL)",
            name="ck_customer_invoices_issue_metadata",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
            name="fk_customer_invoices_organization_customer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_customer_invoice_organization_number"),
        sa.UniqueConstraint("organization_id", "id", name="uq_customer_invoices_organization_id_id"),
    )
    op.create_index(
        "ix_customer_invoices_org_status_due_date",
        "customer_invoices",
        ["organization_id", "status", "due_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_customer_invoices_org_status_due_date", table_name="customer_invoices")
    op.drop_table("customer_invoices")
    op.drop_constraint("uq_customers_organization_id_id", "customers", type_="unique")

