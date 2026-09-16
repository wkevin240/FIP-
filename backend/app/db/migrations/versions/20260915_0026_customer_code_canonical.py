"""Enforce canonical customer codes at the database boundary.

Revision ID: 20260915_0026
Revises: 20260915_0025
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260915_0026"
down_revision: Union[str, None] = "20260915_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_customers_code_canonical",
        "customers",
        "btrim(code) = code AND code = upper(code)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_customers_code_canonical", "customers", type_="check")
