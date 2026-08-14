"""Add transversal append-only audit journal.

Revision ID: 0010_add_transversal_audit
Revises: 0009_add_fixed_assets_management
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0010_add_transversal_audit"
down_revision: str | None = "0009_add_fixed_assets_management"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_sequences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_hash",
            sa.String(length=64),
            nullable=False,
            server_default="" + "0" * 64 + "",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_audit_sequence_organization"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("resource_type", sa.String(length=96), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("transaction_id", sa.String(length=96), nullable=True),
        sa.Column("request_id", sa.String(length=96), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "sequence_number > 0", name="ck_audit_event_sequence_positive"
        ),
        sa.CheckConstraint("action <> ''", name="ck_audit_event_action_not_empty"),
        sa.CheckConstraint(
            "resource_type <> ''", name="ck_audit_event_resource_type_not_empty"
        ),
        sa.CheckConstraint(
            "resource_id <> ''", name="ck_audit_event_resource_id_not_empty"
        ),
        sa.CheckConstraint(
            "length(event_hash) = 64", name="ck_audit_event_hash_length"
        ),
        sa.CheckConstraint(
            "length(previous_hash) = 64", name="ck_audit_event_previous_hash_length"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "sequence_number",
            name="uq_audit_event_organization_sequence",
        ),
        sa.UniqueConstraint("event_hash", name="uq_audit_event_hash"),
    )
    for column in (
        "organization_id",
        "occurred_at",
        "actor_user_id",
        "action",
        "resource_type",
        "resource_id",
        "transaction_id",
        "request_id",
    ):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.create_index(
        "ix_audit_events_organization_occurred",
        "audit_events",
        ["organization_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_organization_resource",
        "audit_events",
        ["organization_id", "resource_type", "resource_id"],
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_no_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_no_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")
    op.drop_table("audit_events")
    op.drop_table("audit_sequences")
