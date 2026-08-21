"""add tenant scoped treasury liquidity alert configurations

Revision ID: 0028_treasury_liquidity_alerts
Revises: 0027_fpa_scenarios
"""

import sqlalchemy as sa
from alembic import op

revision = "0028_treasury_liquidity_alerts"
down_revision = "0027_fpa_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liquidity_alert_configurations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("alert_code", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("threshold_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            "alert_code IN ('LOW_LIQUIDITY','LIQUIDITY_GAP','NEGATIVE_FORECAST','AR_COLLECTION_RISK','AP_PAYMENT_PRESSURE')",
            name="ck_liquidity_alert_config_code",
        ),
        sa.CheckConstraint(
            "threshold_amount IS NULL OR threshold_amount >= 0",
            name="ck_liquidity_alert_config_threshold_non_negative",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_liquidity_alert_config_effective_dates",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "alert_code", name="uq_liquidity_alert_config_org_code"
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_liquidity_alert_config_org_id"
        ),
    )
    op.create_index(
        "ix_liquidity_alert_configurations_organization_id",
        "liquidity_alert_configurations",
        ["organization_id"],
    )
    op.execute("REVOKE ALL ON TABLE public.liquidity_alert_configurations FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.liquidity_alert_configurations TO fip_user"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE ALL ON TABLE public.liquidity_alert_configurations FROM fip_user"
    )
    op.drop_index(
        "ix_liquidity_alert_configurations_organization_id",
        table_name="liquidity_alert_configurations",
    )
    op.drop_table("liquidity_alert_configurations")
