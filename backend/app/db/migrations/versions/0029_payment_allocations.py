"""Add supplier payment allocations after the canonical AR allocations.

Revision ID: 0029_payment_allocations
Revises: 0028_treasury_liquidity_alerts
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_payment_allocations"
down_revision = "0028_treasury_liquidity_alerts"
branch_labels = None
depends_on = None


def _create_supplier_table() -> None:
    op.create_table(
        "supplier_payment_allocations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("supplier_payment_id", sa.String(), nullable=False),
        sa.Column("purchase_invoice_id", sa.String(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("allocation_reference", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "allocated_amount > 0", name="ck_supplier_payment_allocation_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supplier_payment_id"],
            ["supplier_payments.organization_id", "supplier_payments.id"],
            name="fk_supplier_payment_allocation_org_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "purchase_invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_supplier_payment_allocation_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_supplier_payment_allocation_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "supplier_payment_id",
            "purchase_invoice_id",
            name="uq_supplier_payment_allocation_payment_invoice",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_supplier_payment_allocation_idempotency",
        ),
    )


def upgrade() -> None:
    op.alter_column(
        "supplier_payments", "invoice_id", existing_type=sa.String(), nullable=True
    )
    _create_supplier_table()
    op.execute(
        "ALTER TABLE public.supplier_payment_allocations OWNER TO fip_accounting_owner"
    )
    op.execute("REVOKE ALL ON TABLE public.supplier_payment_allocations FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.supplier_payment_allocations TO fip_user"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.supplier_payment_allocations FROM fip_user")
    op.drop_table("supplier_payment_allocations")
    op.alter_column(
        "supplier_payments", "invoice_id", existing_type=sa.String(), nullable=False
    )
