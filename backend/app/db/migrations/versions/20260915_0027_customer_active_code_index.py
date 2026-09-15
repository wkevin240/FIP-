"""Index tenant customer status and code for master-data reads.

Revision ID: 20260915_0027
Revises: 20260915_0026
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260915_0027"
down_revision: Union[str, None] = "20260915_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_customers_organization_active_code",
        "customers",
        ["organization_id", "is_active", "code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_customers_organization_active_code", table_name="customers")
