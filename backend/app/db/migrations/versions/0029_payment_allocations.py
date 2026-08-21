"""add customer and supplier payment allocations

Revision ID: 0029_payment_allocations
Revises: 0028_treasury_liquidity_alerts
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_payment_allocations"
down_revision = "0028_treasury_liquidity_alerts"
branch_labels = None
depends_on = None


def _create_payment_table() -> None:
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("allocation_reference", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "allocated_amount > 0", name="ck_payment_allocation_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["payments.organization_id", "payments.id"],
            name="fk_payment_allocation_org_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_payment_allocation_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_payment_allocation_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "payment_id",
            "invoice_id",
            name="uq_payment_allocation_payment_invoice",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_allocation_idempotency",
        ),
    )


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
    op.alter_column("payments", "invoice_id", existing_type=sa.String(), nullable=True)
    op.alter_column(
        "supplier_payments", "invoice_id", existing_type=sa.String(), nullable=True
    )
    _create_payment_table()
    _create_supplier_table()
    for table in ("public.payment_allocations", "public.supplier_payment_allocations"):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO fip_user")


def downgrade() -> None:
    for table in ("public.supplier_payment_allocations", "public.payment_allocations"):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM fip_user")
        op.drop_table(table.split(".")[-1])
    op.alter_column(
        "supplier_payments", "invoice_id", existing_type=sa.String(), nullable=False
    )
    op.alter_column("payments", "invoice_id", existing_type=sa.String(), nullable=False)
