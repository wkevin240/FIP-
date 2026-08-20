"""Advanced accounts payable allocations.

Revision ID: 0029_ap_advanced_allocations
Revises: 0027_fpa_scenarios
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_ap_advanced_allocations"
down_revision: str | None = "0027_fpa_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(name: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    op.execute(f"ALTER TABLE {name} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {name} FROM PUBLIC")
    op.execute(f"GRANT {grants} ON TABLE {name} TO fip_user")


def upgrade() -> None:
    op.alter_column("supplier_payments", "invoice_id", nullable=True)
    op.create_table(
        "supplier_payment_allocations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "payment_id"],
            ["supplier_payments.organization_id", "supplier_payments.id"],
            name="fk_supplier_payment_allocation_org_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_supplier_payment_allocation_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            name="fk_supplier_payment_allocation_org_supplier",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "payment_id",
            "invoice_id",
            name="uq_supplier_payment_allocation_pair",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_supplier_payment_allocation_idempotency",
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_supplier_payment_allocation_positive"
        ),
    )
    _secure("supplier_payment_allocations")
    for column in ("organization_id", "payment_id", "invoice_id", "supplier_id"):
        op.create_index(
            f"ix_supplier_payment_allocations_{column}",
            "supplier_payment_allocations",
            [column],
        )

    op.execute(
        """
        INSERT INTO supplier_payment_allocations
            (id, created_at, updated_at, organization_id, payment_id, invoice_id,
             supplier_id, amount, idempotency_key, created_by_user_id)
        SELECT
            'legacy-' || sp.id,
            sp.created_at,
            sp.updated_at,
            sp.organization_id,
            sp.id,
            sp.invoice_id,
            pi.supplier_id,
            sp.amount,
            'legacy-' || sp.organization_id || '-' || sp.id,
            NULL
        FROM supplier_payments sp
        JOIN purchase_invoices pi
          ON pi.organization_id = sp.organization_id
         AND pi.id = sp.invoice_id
        WHERE sp.invoice_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_payment_allocations_supplier_id",
        table_name="supplier_payment_allocations",
    )
    op.drop_index(
        "ix_supplier_payment_allocations_invoice_id",
        table_name="supplier_payment_allocations",
    )
    op.drop_index(
        "ix_supplier_payment_allocations_payment_id",
        table_name="supplier_payment_allocations",
    )
    op.drop_index(
        "ix_supplier_payment_allocations_organization_id",
        table_name="supplier_payment_allocations",
    )
    op.drop_table("supplier_payment_allocations")
    op.alter_column("supplier_payments", "invoice_id", nullable=False)
