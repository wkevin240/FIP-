"""Enforce supplier invoice approval identity consistency.

Revision ID: 20260916_0031
Revises: 20260916_0030
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260916_0031"
down_revision: Union[str, None] = "20260916_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_supplier_invoice_approval_identity",
        "supplier_invoices",
        "(status = 'APPROVED' AND approved_by IS NOT NULL) OR (status <> 'APPROVED' AND approved_by IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_supplier_invoice_approval_identity",
        "supplier_invoices",
        type_="check",
    )
