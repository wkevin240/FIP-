"""Add inventory reference data, valued balances and stock movements.

Revision ID: 0005_add_inventory
Revises: 0004_add_vat
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_inventory"
down_revision: str | None = "0004_add_vat"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("reorder_point", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "reorder_point >= 0", name="ck_product_reorder_point_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "sku", name="uq_product_organization_sku"
        ),
    )
    op.create_index("ix_products_organization_id", "products", ["organization_id"])

    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_warehouse_organization_code"
        ),
    )
    op.create_index("ix_warehouses_organization_id", "warehouses", ["organization_id"])

    op.create_table(
        "stock_balances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("warehouse_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "average_unit_cost", sa.Numeric(precision=18, scale=4), nullable=False
        ),
        sa.CheckConstraint(
            "average_unit_cost >= 0",
            name="ck_stock_balance_average_cost_non_negative",
        ),
        sa.CheckConstraint(
            "quantity >= 0", name="ck_stock_balance_quantity_non_negative"
        ),
        sa.CheckConstraint(
            "total_value >= 0", name="ck_stock_balance_total_value_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "warehouse_id",
            "product_id",
            name="uq_stock_balance_organization_warehouse_product",
        ),
    )
    op.create_index(
        "ix_stock_balances_organization_id", "stock_balances", ["organization_id"]
    )
    op.create_index("ix_stock_balances_product_id", "stock_balances", ["product_id"])
    op.create_index(
        "ix_stock_balances_warehouse_id", "stock_balances", ["warehouse_id"]
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("warehouse_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("transfer_id", sa.String(length=36), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "movement_type IN ('RECEIPT', 'ISSUE', 'ADJUSTMENT_IN', "
            "'ADJUSTMENT_OUT', 'TRANSFER_IN', 'TRANSFER_OUT')",
            name="ck_stock_movement_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movement_quantity_positive"),
        sa.CheckConstraint(
            "total_value >= 0", name="ck_stock_movement_total_value_non_negative"
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name="ck_stock_movement_unit_cost_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stock_movements_movement_date", "stock_movements", ["movement_date"]
    )
    op.create_index(
        "ix_stock_movements_movement_type", "stock_movements", ["movement_type"]
    )
    op.create_index(
        "ix_stock_movements_organization_id", "stock_movements", ["organization_id"]
    )
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index(
        "ix_stock_movements_transfer_id", "stock_movements", ["transfer_id"]
    )
    op.create_index(
        "ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_warehouse_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_transfer_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_product_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_organization_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_movement_type", table_name="stock_movements")
    op.drop_index("ix_stock_movements_movement_date", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index("ix_stock_balances_warehouse_id", table_name="stock_balances")
    op.drop_index("ix_stock_balances_product_id", table_name="stock_balances")
    op.drop_index("ix_stock_balances_organization_id", table_name="stock_balances")
    op.drop_table("stock_balances")
    op.drop_index("ix_warehouses_organization_id", table_name="warehouses")
    op.drop_table("warehouses")
    op.drop_index("ix_products_organization_id", table_name="products")
    op.drop_table("products")
