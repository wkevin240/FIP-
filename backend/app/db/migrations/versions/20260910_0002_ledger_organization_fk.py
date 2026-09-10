"""Complete tenant isolation for ledger postings.

Revision ID: 20260910_0002
Revises: 20260910_0001
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260910_0002"
down_revision: Union[str, None] = "20260910_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_ledger_postings_organization_id_organizations",
        "ledger_postings",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ledger_postings_organization_id_organizations",
        "ledger_postings",
        type_="foreignkey",
    )
