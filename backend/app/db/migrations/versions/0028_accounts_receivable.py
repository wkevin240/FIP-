"""Add Accounts Receivable allocations and ageing support.

Revision ID: 0028_accounts_receivable
Revises: 0027_fpa_scenarios
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_accounts_receivable"
down_revision: str | None = "0027_fpa_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    op.execute(f"ALTER TABLE public.{name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE public.{name} FROM PUBLIC")
    op.execute(f"GRANT {grants} ON TABLE public.{name} TO fip_user")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.payments DROP CONSTRAINT IF EXISTS payments_invoice_id_fkey"
    )
    op.alter_column("payments", "invoice_id", existing_type=sa.String(), nullable=True)
    op.create_foreign_key(
        "fk_payment_org_invoice",
        "payments",
        "invoices",
        ["organization_id", "invoice_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocated_at", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("allocated_by_user_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_payment_allocations_org_id"
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
        sa.CheckConstraint("amount > 0", name="ck_payment_allocation_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["payments.organization_id", "payments.id"],
            name="fk_payment_allocation_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["invoices.organization_id", "invoices.id"],
            name="fk_payment_allocation_invoice",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["allocated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_payment_allocations_organization_id",
        "payment_allocations",
        ["organization_id"],
    )
    op.create_index(
        "ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"]
    )
    op.create_index(
        "ix_payment_allocations_invoice_id", "payment_allocations", ["invoice_id"]
    )
    _secure("payment_allocations")
    op.execute(
        """
        INSERT INTO public.payment_allocations
            (id, created_at, updated_at, organization_id, payment_id, invoice_id,
             amount, allocated_at, idempotency_key, allocated_by_user_id)
        SELECT
            'legacy-payment-allocation-' || p.id,
            p.created_at,
            p.updated_at,
            p.organization_id,
            p.id,
            p.invoice_id,
            p.amount,
            COALESCE(p.received_at::text, p.payment_date::text),
            'payment:' || p.id || ':initial',
            NULL
        FROM public.payments p
        WHERE p.invoice_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_payment_org_invoice", "payments", type_="foreignkey")
    op.create_foreign_key(
        "payments_invoice_id_fkey",
        "payments",
        "invoices",
        ["invoice_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index("ix_payment_allocations_invoice_id", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_payment_id", table_name="payment_allocations")
    op.drop_index(
        "ix_payment_allocations_organization_id", table_name="payment_allocations"
    )
    op.drop_table("payment_allocations")
    op.alter_column("payments", "invoice_id", existing_type=sa.String(), nullable=False)
