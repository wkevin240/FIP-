"""Add supplier procurement and accounting posting workflow.

Revision ID: 0023_procurement_invoices
Revises: 0022_bank_rules_accounting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_procurement_invoices"
down_revision: str | None = "0022_bank_rules_accounting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str) -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("supplier_code", sa.String(64), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("tax_id", sa.String(64)),
        sa.Column("address", sa.Text()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "supplier_code", name="uq_supplier_org_code"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_supplier_org_id"),
    )
    _secure("suppliers")
    op.create_table(
        "purchase_invoices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_purchase_invoice_org_supplier",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id", "invoice_number", name="uq_purchase_invoice_org_number"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_purchase_invoice_org_id"),
        sa.CheckConstraint(
            "subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0",
            name="ck_purchase_invoice_amounts_non_negative",
        ),
        sa.CheckConstraint(
            "total_amount = subtotal + tax_amount",
            name="ck_purchase_invoice_total_consistency",
        ),
        sa.CheckConstraint(
            "paid_amount >= 0 AND paid_amount <= total_amount",
            name="ck_purchase_invoice_paid_bounds",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','VALIDATED','PARTIALLY_PAID','PAID','CANCELLED')",
            name="ck_purchase_invoice_status",
        ),
    )
    _secure("purchase_invoices")
    op.create_table(
        "purchase_invoice_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("expense_account_id", sa.String(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_purchase_line_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_line_quantity_positive"),
        sa.CheckConstraint(
            "unit_price >= 0 AND tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_line_values",
        ),
        sa.CheckConstraint(
            "line_subtotal >= 0 AND tax_amount >= 0 AND line_total = line_subtotal + tax_amount",
            name="ck_purchase_line_totals",
        ),
        sa.CheckConstraint("sort_order > 0", name="ck_purchase_line_sort_order"),
    )
    _secure("purchase_invoice_lines")
    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("external_reference", sa.String(128), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_supplier_payment_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_supplier_payment_org_external",
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_supplier_payment_org_id"),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payment_amount_positive"),
    )
    _secure("supplier_payments")
    op.create_table(
        "procurement_accounting_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("payable_account_id", sa.String(), nullable=False),
        sa.Column("deductible_vat_account_id", sa.String()),
        sa.Column("settlement_account_id", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_id"],
            ["journals.organization_id", "journals.id"],
            name="fk_procurement_profile_org_journal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "payable_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_payable",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "deductible_vat_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_vat",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "settlement_account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_procurement_profile_org_settlement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", name="uq_procurement_profile_org"),
    )
    _secure("procurement_accounting_profiles")
    for name, source, source_type in (
        (
            "purchase_invoice_accounting_postings",
            "purchase_invoices",
            "PURCHASE_INVOICE",
        ),
        (
            "supplier_payment_accounting_postings",
            "supplier_payments",
            "SUPPLIER_PAYMENT",
        ),
    ):
        op.create_table(
            name,
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column(
                "organization_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("source_module", sa.String(64), nullable=False),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_id", sa.String(), nullable=False),
            sa.Column("journal_entry_id", sa.String(), nullable=False),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id", "source_id"],
                [f"{source}.organization_id", f"{source}.id"],
                name=f"fk_{name}_source",
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id", "journal_entry_id"],
                ["journal_entries.organization_id", "journal_entries.id"],
                name=f"fk_{name}_entry",
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint(
                "organization_id", "source_id", name=f"uq_{name}_source"
            ),
            sa.UniqueConstraint(
                "organization_id", "idempotency_key", name=f"uq_{name}_key"
            ),
            sa.CheckConstraint(
                f"source_module = 'PROCUREMENT' AND source_type = '{source_type}' AND status = 'POSTED'",
                name=f"ck_{name}_identity",
            ),
        )
        _secure(name)


def downgrade() -> None:
    for name in (
        "supplier_payment_accounting_postings",
        "purchase_invoice_accounting_postings",
        "procurement_accounting_profiles",
        "supplier_payments",
        "purchase_invoice_lines",
        "purchase_invoices",
        "suppliers",
    ):
        op.drop_table(name)
