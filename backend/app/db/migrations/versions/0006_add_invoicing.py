"""Add invoicing, credit notes and payment tracking.

Revision ID: 0006_add_invoicing
Revises: 0005_add_inventory
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_invoicing"
down_revision: str | None = "0005_add_inventory"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_tax_id", sa.String(length=64), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("credited_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "credited_amount >= 0", name="ck_invoice_credited_non_negative"
        ),
        sa.CheckConstraint("paid_amount >= 0", name="ck_invoice_paid_non_negative"),
        sa.CheckConstraint(
            "paid_amount + credited_amount <= total_amount",
            name="ck_invoice_settlement_within_total",
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoice_tax_non_negative"),
        sa.CheckConstraint("total_amount >= 0", name="ck_invoice_total_non_negative"),
        sa.CheckConstraint(
            "total_amount = subtotal + tax_amount", name="ck_invoice_total_consistency"
        ),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_invoice_due_date",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')",
            name="ck_invoice_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "invoice_number", name="uq_invoice_organization_number"
        ),
    )
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("vat_rate_id", sa.String(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "line_subtotal >= 0", name="ck_invoice_line_subtotal_non_negative"
        ),
        sa.CheckConstraint(
            "line_total >= 0", name="ck_invoice_line_total_non_negative"
        ),
        sa.CheckConstraint(
            "line_total = line_subtotal + tax_amount",
            name="ck_invoice_line_total_consistency",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_line_quantity_positive"),
        sa.CheckConstraint(
            "sort_order > 0", name="ck_invoice_line_sort_order_positive"
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoice_line_tax_non_negative"),
        sa.CheckConstraint("tax_rate <= 100", name="ck_invoice_line_tax_rate_maximum"),
        sa.CheckConstraint(
            "tax_rate >= 0", name="ck_invoice_line_tax_rate_non_negative"
        ),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_invoice_line_unit_price_non_negative"
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vat_rate_id"], ["vat_rates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_product_id", "invoice_lines", ["product_id"])
    op.create_index("ix_invoice_lines_vat_rate_id", "invoice_lines", ["vat_rate_id"])

    op.create_table(
        "credit_notes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("credit_note_number", sa.String(length=64), nullable=False),
        sa.Column("credit_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_credit_note_amount_positive"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "credit_note_number",
            name="uq_credit_note_organization_number",
        ),
    )
    op.create_index("ix_credit_notes_credit_date", "credit_notes", ["credit_date"])
    op.create_index("ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"])
    op.create_index(
        "ix_credit_notes_organization_id", "credit_notes", ["organization_id"]
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("external_reference", sa.String(length=100), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        sa.CheckConstraint(
            "method IN ('CASH', 'BANK_TRANSFER', 'CARD', 'MOBILE_MONEY', 'OTHER')",
            name="ck_payment_method",
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_payment_organization_external",
        ),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_organization_id", "payments", ["organization_id"])
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])


def downgrade() -> None:
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_payments_organization_id", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_credit_notes_organization_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_invoice_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_credit_date", table_name="credit_notes")
    op.drop_table("credit_notes")
    op.drop_index("ix_invoice_lines_vat_rate_id", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_product_id", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_organization_id", table_name="invoices")
    op.drop_index("ix_invoices_invoice_date", table_name="invoices")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_table("invoices")
