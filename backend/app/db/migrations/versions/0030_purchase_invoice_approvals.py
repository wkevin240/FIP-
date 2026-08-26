"""Add purchase invoice approval workflow.

Revision ID: 0030_purchase_invoice_approvals
Revises: 0029_ap_advanced_allocations
"""

import sqlalchemy as sa
from alembic import op

revision = "0030_purchase_invoice_approvals"
down_revision = "0029_ap_advanced_allocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_invoice_approvals",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("purchase_invoice_id", sa.String(), nullable=False),
        sa.Column("requester_user_id", sa.String(), nullable=False),
        sa.Column("approver_user_id", sa.String(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="PENDING"
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "purchase_invoice_id"],
            ["purchase_invoices.organization_id", "purchase_invoices.id"],
            name="fk_purchase_invoice_approval_org_invoice",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "purchase_invoice_id",
            name="uq_purchase_invoice_approval_org_invoice",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_purchase_invoice_approval_status",
        ),
        sa.CheckConstraint(
            "status = 'PENDING' OR decided_at IS NOT NULL",
            name="ck_purchase_invoice_approval_decided_at",
        ),
        sa.CheckConstraint(
            "status = 'PENDING' OR approver_user_id IS NOT NULL",
            name="ck_purchase_invoice_approval_approver",
        ),
        sa.CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> requester_user_id",
            name="ck_purchase_invoice_approval_separation",
        ),
    )
    op.create_index(
        "ix_purchase_invoice_approvals_organization_id",
        "purchase_invoice_approvals",
        ["organization_id"],
    )
    op.create_index(
        "ix_purchase_invoice_approvals_purchase_invoice_id",
        "purchase_invoice_approvals",
        ["purchase_invoice_id"],
    )
    op.create_index(
        "ix_purchase_invoice_approvals_requester_user_id",
        "purchase_invoice_approvals",
        ["requester_user_id"],
    )
    op.create_index(
        "ix_purchase_invoice_approvals_approver_user_id",
        "purchase_invoice_approvals",
        ["approver_user_id"],
    )
    op.create_index(
        "ix_purchase_invoice_approvals_status",
        "purchase_invoice_approvals",
        ["status"],
    )
    op.execute("REVOKE ALL ON TABLE public.purchase_invoice_approvals FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.purchase_invoice_approvals TO fip_user"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.purchase_invoice_approvals FROM fip_user")
    op.execute("DROP TABLE IF EXISTS public.purchase_invoice_approvals")
