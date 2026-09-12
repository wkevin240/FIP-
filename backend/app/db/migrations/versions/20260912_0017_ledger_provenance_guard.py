"""Keep ledger postings attached to their exact posted journal source.

Revision ID: 20260912_0017
Revises: 20260912_0016
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260912_0017"
down_revision: Union[str, None] = "20260912_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fip_ledger_posting_validate_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            source_status text;
            source_organization_id text;
            source_fiscal_period_id text;
            source_account_id text;
            source_posting_date date;
            source_line_number integer;
            source_debit numeric;
            source_credit numeric;
        BEGIN
            SELECT
                je.status::text,
                je.organization_id,
                je.fiscal_period_id,
                jel.account_id,
                je.entry_date,
                jel.line_number,
                jel.debit,
                jel.credit
            INTO
                source_status,
                source_organization_id,
                source_fiscal_period_id,
                source_account_id,
                source_posting_date,
                source_line_number,
                source_debit,
                source_credit
            FROM journal_entries AS je
            JOIN journal_entry_lines AS jel
              ON jel.id = NEW.journal_entry_line_id
             AND jel.journal_entry_id = je.id
            WHERE je.id = NEW.journal_entry_id;

            IF source_status IS NULL THEN
                RAISE EXCEPTION 'ledger posting source journal entry and line do not match'
                    USING ERRCODE = '23503';
            END IF;

            IF source_status <> 'POSTED' THEN
                RAISE EXCEPTION 'ledger postings require a POSTED journal entry'
                    USING ERRCODE = '23514';
            END IF;

            IF source_organization_id <> NEW.organization_id
               OR source_fiscal_period_id <> NEW.fiscal_period_id
               OR source_account_id <> NEW.account_id
               OR source_posting_date <> NEW.posting_date
               OR source_line_number <> NEW.line_number
               OR source_debit <> NEW.debit
               OR source_credit <> NEW.credit THEN
                RAISE EXCEPTION 'ledger posting does not match its journal source line'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ledger_postings_validate_provenance
        BEFORE INSERT
        ON ledger_postings
        FOR EACH ROW EXECUTE FUNCTION fip_ledger_posting_validate_provenance();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ledger_postings_validate_provenance ON ledger_postings"
    )
    op.execute("DROP FUNCTION IF EXISTS fip_ledger_posting_validate_provenance()")
