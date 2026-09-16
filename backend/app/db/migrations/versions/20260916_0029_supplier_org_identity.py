"""Add organization/id identity key required by tenant-scoped supplier references.

Revision ID: 20260916_0029
Revises: 20260916_0028
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260916_0029"
down_revision: Union[str, None] = "20260916_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_supplier_organization_id",
        "suppliers",
        ["organization_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_supplier_organization_id", "suppliers", type_="unique")
