"""Add purchase request, order and goods receipt workflow.

Revision ID: 0031_procurement_flow
Revises: 0030_purchase_invoice_approvals
"""

import sqlalchemy as sa
from alembic import op

revision = "0031_procurement_flow"
down_revision = "0030_purchase_invoice_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_requests",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("request_number", sa.String(64), nullable=False),
        sa.Column("requester_user_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "request_number", name="uq_purchase_request_org_number"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_purchase_request_org_id"),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','CANCELLED')",
            name="ck_purchase_request_status",
        ),
    )
    op.create_table(
        "purchase_request_lines",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("estimated_unit_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["purchase_requests.organization_id", "purchase_requests.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_request_line_quantity"),
    )
    op.create_table(
        "purchase_orders",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["purchase_requests.organization_id", "purchase_requests.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "order_number", name="uq_purchase_order_org_number"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_purchase_order_org_id"),
        sa.CheckConstraint(
            "status IN ('DRAFT','ISSUED','CANCELLED','CLOSED')",
            name="ck_purchase_order_status",
        ),
    )
    op.create_table(
        "purchase_order_lines",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["purchase_orders.organization_id", "purchase_orders.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_purchase_order_line_org_id"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_order_line_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_purchase_order_line_price"),
    )
    op.create_table(
        "goods_receipts",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("receipt_number", sa.String(64), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("receiver_user_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "order_id"],
            ["purchase_orders.organization_id", "purchase_orders.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "receipt_number", name="uq_goods_receipt_org_number"
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_goods_receipt_org_id"),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','CANCELLED')", name="ck_goods_receipt_status"
        ),
    )
    op.create_table(
        "goods_receipt_lines",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("receipt_id", sa.String(), nullable=False),
        sa.Column("order_line_id", sa.String(), nullable=False),
        sa.Column("received_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "receipt_id"],
            ["goods_receipts.organization_id", "goods_receipts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "order_line_id"],
            ["purchase_order_lines.organization_id", "purchase_order_lines.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "received_quantity > 0", name="ck_goods_receipt_line_quantity"
        ),
    )
    op.add_column(
        "purchase_invoices", sa.Column("purchase_order_id", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_purchase_invoices_purchase_order_id",
        "purchase_invoices",
        ["purchase_order_id"],
    )
    op.create_foreign_key(
        "fk_purchase_invoice_org_order",
        "purchase_invoices",
        "purchase_orders",
        ["organization_id", "purchase_order_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "REVOKE ALL ON TABLE public.purchase_requests, public.purchase_request_lines, public.purchase_orders, public.purchase_order_lines, public.goods_receipts, public.goods_receipt_lines FROM PUBLIC"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.purchase_requests, public.purchase_request_lines, public.purchase_orders, public.purchase_order_lines, public.goods_receipts, public.goods_receipt_lines TO fip_user"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE ALL ON TABLE public.purchase_requests, public.purchase_request_lines, public.purchase_orders, public.purchase_order_lines, public.goods_receipts, public.goods_receipt_lines FROM fip_user"
    )
    op.drop_constraint(
        "fk_purchase_invoice_org_order", "purchase_invoices", type_="foreignkey"
    )
    op.drop_index(
        "ix_purchase_invoices_purchase_order_id", table_name="purchase_invoices"
    )
    op.drop_column("purchase_invoices", "purchase_order_id")
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("purchase_request_lines")
    op.drop_table("purchase_requests")
