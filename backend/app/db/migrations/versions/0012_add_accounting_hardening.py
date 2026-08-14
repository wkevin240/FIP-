"""Add professional accounting hardening flows.

Revision ID: 0012_accounting_hardening
Revises: 0011_accounting_integrity_p0
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_accounting_hardening"
down_revision: str | None = "0011_accounting_integrity_p0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def upgrade() -> None:
    op.add_column(
        "journal_entries", sa.Column("reversal_of_id", sa.String(), nullable=True)
    )
    op.add_column(
        "journal_entries", sa.Column("reversal_reason", sa.String(500), nullable=True)
    )
    op.add_column(
        "journal_entries",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "journal_entries", sa.Column("voided_by_user_id", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_journal_entries_reversal_of_id", "journal_entries", ["reversal_of_id"]
    )
    op.create_unique_constraint(
        "uq_journal_entries_organization_reversal_of",
        "journal_entries",
        ["organization_id", "reversal_of_id"],
    )
    op.create_foreign_key(
        "fk_journal_entries_organization_reversal_of",
        "journal_entries",
        "journal_entries",
        ["organization_id", "reversal_of_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_journal_entry_integrity()
        RETURNS trigger AS $$
        DECLARE
            debit_total numeric(18, 2);
            credit_total numeric(18, 2);
            line_count integer;
            period_status fiscalperiodstatus;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('POSTED', 'VOIDED') THEN
                    RAISE EXCEPTION 'posted or voided journal entries are immutable';
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'DRAFT' OR NEW.posted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'journal entries must be created as draft entries';
                END IF;
                IF NEW.reversal_of_id IS NULL AND NEW.reversal_reason IS NOT NULL THEN
                    RAISE EXCEPTION 'reversal reason requires an original journal entry';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'VOIDED' THEN
                RAISE EXCEPTION 'posted or voided journal entries are immutable';
            END IF;
            IF OLD.status = 'POSTED' THEN
                IF NEW.status <> 'VOIDED' OR current_user <> 'fip_accounting_owner' THEN
                    RAISE EXCEPTION 'posted or voided journal entries are immutable';
                END IF;
                IF NEW.voided_at IS NULL OR NEW.voided_by_user_id IS NULL THEN
                    RAISE EXCEPTION 'voided journal entries require actor and timestamp';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM public.journal_entries AS reversal
                    WHERE reversal.organization_id = OLD.organization_id
                      AND reversal.reversal_of_id = OLD.id
                      AND reversal.status = 'POSTED'
                ) THEN
                    RAISE EXCEPTION 'voiding requires a posted reversal entry';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'DRAFT' AND NEW.status <> OLD.status THEN
                IF NEW.status <> 'POSTED' OR current_user <> 'fip_accounting_owner' THEN
                    RAISE EXCEPTION 'draft journal entries can only transition to POSTED';
                END IF;
                IF NEW.posted_at IS NULL THEN
                    RAISE EXCEPTION 'posted journal entries require posted_at';
                END IF;
                SELECT status INTO period_status
                FROM public.fiscal_periods
                WHERE id = NEW.fiscal_period_id AND organization_id = NEW.organization_id;
                IF period_status <> 'OPEN' THEN
                    RAISE EXCEPTION 'journal entries can only be posted in open fiscal periods';
                END IF;
                SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                INTO line_count, debit_total, credit_total
                FROM public.journal_entry_lines
                WHERE journal_entry_id = NEW.id AND organization_id = NEW.organization_id;
                IF line_count < 2 OR debit_total <> credit_total THEN
                    RAISE EXCEPTION 'posted journal entries must have balanced lines';
                END IF;
            END IF;
            IF NEW.status = 'DRAFT' AND NEW.posted_at IS NOT NULL THEN
                RAISE EXCEPTION 'draft journal entries cannot have posted_at';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        SET search_path = pg_catalog, public;
        """
    )
    op.execute(
        """
        CREATE FUNCTION void_journal_entry(target_entry_id text, actor_id text)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM public.accounting_security_credentials
                WHERE credential_key = 'posting'
                  AND secret_hash = encode(
                      digest(current_setting('fip.posting_token', true), 'sha256'),
                      'hex'
                  )
            ) THEN
                RAISE EXCEPTION 'journal entry void authorization failed';
            END IF;
            UPDATE public.journal_entries AS original
            SET status = 'VOIDED', voided_at = CURRENT_TIMESTAMP, voided_by_user_id = actor_id
            WHERE original.id = target_entry_id
              AND original.status = 'POSTED'
              AND EXISTS (
                  SELECT 1 FROM public.journal_entries AS reversal
                  WHERE reversal.organization_id = original.organization_id
                    AND reversal.reversal_of_id = original.id
                    AND reversal.status = 'POSTED'
              );
            IF NOT FOUND THEN
                RAISE EXCEPTION 'posted journal entry with posted reversal not found';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        f"ALTER FUNCTION void_journal_entry(text, text) OWNER TO {ACCOUNTING_OWNER_ROLE}"
    )
    op.execute("REVOKE ALL ON FUNCTION void_journal_entry(text, text) FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION void_journal_entry(text, text) TO {APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS void_journal_entry(text, text)")
    op.drop_constraint(
        "fk_journal_entries_organization_reversal_of",
        "journal_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_journal_entries_organization_reversal_of", "journal_entries", type_="unique"
    )
    op.drop_index("ix_journal_entries_reversal_of_id", "journal_entries")
    op.drop_column("journal_entries", "voided_by_user_id")
    op.drop_column("journal_entries", "voided_at")
    op.drop_column("journal_entries", "reversal_reason")
    op.drop_column("journal_entries", "reversal_of_id")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_journal_entry_integrity()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status IN ('POSTED', 'VOIDED') THEN
                RAISE EXCEPTION 'posted or voided journal entries are immutable';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.status IN ('POSTED', 'VOIDED') THEN
                RAISE EXCEPTION 'posted or voided journal entries are immutable';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql SET search_path = pg_catalog, public;
        """
    )
