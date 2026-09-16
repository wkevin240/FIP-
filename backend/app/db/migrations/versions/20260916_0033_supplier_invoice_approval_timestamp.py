"""Track supplier invoice approval timestamp and enforce transition integrity.

Revision ID: 20260916_0033
Revises: 20260916_0032
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260916_0033"
down_revision: Union[str, None] = "20260916_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "supplier_invoices",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_supplier_invoice_approval_timestamp()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.status = 'APPROVED' AND NEW.approved_at IS NULL THEN
                RAISE EXCEPTION 'approved_at is required for approved supplier invoices'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.status <> 'APPROVED' AND NEW.approved_at IS NOT NULL THEN
                RAISE EXCEPTION 'approved_at must be null for non-approved supplier invoices'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_supplier_invoice_approval_timestamp
        BEFORE INSERT OR UPDATE OF status, approved_at
        ON supplier_invoices
        FOR EACH ROW
        EXECUTE FUNCTION enforce_supplier_invoice_approval_timestamp();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_supplier_invoice_approval_timestamp ON supplier_invoices"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS enforce_supplier_invoice_approval_timestamp()"
    )
    op.drop_column("supplier_invoices", "approved_at")
