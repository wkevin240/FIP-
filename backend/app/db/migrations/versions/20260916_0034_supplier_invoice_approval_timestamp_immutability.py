"""Protect supplier invoice approval timestamps from mutation.

Revision ID: 20260916_0034
Revises: 20260916_0033
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260916_0034"
down_revision: Union[str, None] = "20260916_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            IF OLD.status = 'APPROVED'
               AND NEW.status = 'APPROVED'
               AND NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
                RAISE EXCEPTION 'approved_at cannot be changed after supplier invoice approval'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
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
