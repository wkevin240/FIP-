"""Enforce canonical supplier invoice currency codes.

Revision ID: 20260916_0032
Revises: 20260916_0031
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260916_0032"
down_revision: Union[str, None] = "20260916_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_supplier_invoice_currency_code_canonical",
        "supplier_invoices",
        "currency_code ~ '^[A-Z]{3}$'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_supplier_invoice_currency_code_canonical",
        "supplier_invoices",
        type_="check",
    )
