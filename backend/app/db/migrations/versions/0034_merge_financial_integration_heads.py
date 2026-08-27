"""Merge the treasury and financial integration migration branches.

Revision ID: 0034_merge_heads
Revises: 0028_treasury_liquidity_alerts, 0033_alloc_compat
"""

from collections.abc import Sequence

revision: str = "0034_merge_heads"
down_revision: str | Sequence[str] | None = (
    "0028_treasury_liquidity_alerts",
    "0033_alloc_compat",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
