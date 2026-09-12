"""Enforce fiscal-period ownership, bounds, and non-overlap in PostgreSQL.

Revision ID: 20260912_0014
Revises: 20260912_0013
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0014"
down_revision: Union[str, None] = "20260912_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_fiscal_period_validate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            year_start date;
            year_end date;
        BEGIN
            SELECT start_date, end_date
            INTO year_start, year_end
            FROM fiscal_years
            WHERE id = NEW.fiscal_year_id
              AND organization_id = NEW.organization_id
            FOR UPDATE;

            IF year_start IS NULL THEN
                RAISE EXCEPTION 'fiscal period fiscal year does not exist for the organization'
                    USING ERRCODE = '23503';
            END IF;

            IF NEW.start_date < year_start OR NEW.end_date > year_end THEN
                RAISE EXCEPTION 'fiscal period dates must be contained within the fiscal year'
                    USING ERRCODE = '23514';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM fiscal_periods AS existing
                WHERE existing.organization_id = NEW.organization_id
                  AND existing.fiscal_year_id = NEW.fiscal_year_id
                  AND existing.id <> NEW.id
                  AND existing.start_date <= NEW.end_date
                  AND existing.end_date >= NEW.start_date
            ) THEN
                RAISE EXCEPTION 'fiscal period dates overlap an existing period'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_fiscal_period_validate
        BEFORE INSERT OR UPDATE OF organization_id, fiscal_year_id, start_date, end_date
        ON fiscal_periods
        FOR EACH ROW EXECUTE FUNCTION fip_fiscal_period_validate();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_fiscal_period_validate ON fiscal_periods")
    op.execute("DROP FUNCTION IF EXISTS fip_fiscal_period_validate()")
