"""Add compatibility metadata to canonical supplier payment allocations.

Revision ID: 0033_supplier_payment_allocation_compatibility
Revises: 0032_profitability_mappings
"""

import sqlalchemy as sa
from alembic import op

revision = "0033_supplier_payment_allocation_compatibility"
down_revision = "0032_profitability_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_payment_allocations",
        sa.Column("allocation_reference", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("supplier_payment_allocations", "allocation_reference")
