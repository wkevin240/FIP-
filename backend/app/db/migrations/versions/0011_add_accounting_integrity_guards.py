"""Add PostgreSQL accounting integrity guards.

Revision ID: 0011_accounting_integrity_p0
Revises: 0010_add_transversal_audit
Create Date: 2026-08-14
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_accounting_integrity_p0"
down_revision: str | None = "0010_add_transversal_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPLICATION_ROLE = "fip_user"
DATABASE_OWNER_ROLE = "fip_database_owner"
ACCOUNTING_OWNER_ROLE = "fip_accounting_owner"


def upgrade() -> None:
    posting_token = os.environ.get("ACCOUNTING_POSTING_TOKEN")
    if not posting_token:
        raise RuntimeError(
            "ACCOUNTING_POSTING_TOKEN must be configured before applying "
            "the accounting integrity migration"
        )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{DATABASE_OWNER_ROLE}'
            ) THEN
                CREATE ROLE {DATABASE_OWNER_ROLE}
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{ACCOUNTING_OWNER_ROLE}'
            ) THEN
                CREATE ROLE {ACCOUNTING_OWNER_ROLE}
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        f"ALTER DATABASE {op.get_bind().engine.url.database} OWNER TO {DATABASE_OWNER_ROLE}"
    )
    op.execute(f"ALTER SCHEMA public OWNER TO {DATABASE_OWNER_ROLE}")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "accounting_security_credentials",
        sa.Column("credential_key", sa.String(length=64), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "credential_key <> ''", name="ck_accounting_security_credential_key"
        ),
        sa.CheckConstraint(
            "length(secret_hash) = 64", name="ck_accounting_security_secret_hash"
        ),
        sa.PrimaryKeyConstraint("credential_key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO accounting_security_credentials "
            "(credential_key, secret_hash) "
            "VALUES ('posting', encode(digest(:posting_token, 'sha256'), 'hex'))"
        ).bindparams(posting_token=posting_token)
    )

    for table_name in (
        "accounts",
        "fiscal_years",
        "fiscal_periods",
        "journals",
        "journal_entries",
        "journal_entry_lines",
        "period_closings",
        "accounting_security_credentials",
    ):
        op.execute(f"ALTER TABLE {table_name} OWNER TO {ACCOUNTING_OWNER_ROLE}")

    op.add_column(
        "journal_entry_lines",
        sa.Column("organization_id", sa.String(), nullable=True),
    )
    op.execute(
        """
        UPDATE journal_entry_lines AS line
        SET organization_id = entry.organization_id
        FROM journal_entries AS entry
        WHERE entry.id = line.journal_entry_id
        """
    )
    op.alter_column("journal_entry_lines", "organization_id", nullable=False)
    op.create_index(
        "ix_journal_entry_lines_organization_id",
        "journal_entry_lines",
        ["organization_id"],
    )

    for table_name in ("accounts", "fiscal_years", "fiscal_periods", "journals"):
        op.create_unique_constraint(
            f"uq_{table_name}_organization_id_id",
            table_name,
            ["organization_id", "id"],
        )
    op.create_unique_constraint(
        "uq_journal_entries_organization_id_id",
        "journal_entries",
        ["organization_id", "id"],
    )

    op.create_foreign_key(
        "fk_fiscal_periods_organization_year",
        "fiscal_periods",
        "fiscal_years",
        ["organization_id", "fiscal_year_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_journal_entries_organization_journal",
        "journal_entries",
        "journals",
        ["organization_id", "journal_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_journal_entries_organization_period",
        "journal_entries",
        "fiscal_periods",
        ["organization_id", "fiscal_period_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_journal_entry_lines_organization_entry",
        "journal_entry_lines",
        "journal_entries",
        ["organization_id", "journal_entry_id"],
        ["organization_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_journal_entry_lines_organization_account",
        "journal_entry_lines",
        "accounts",
        ["organization_id", "account_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_fiscal_period_integrity()
        RETURNS trigger AS $$
        DECLARE
            fiscal_year_status fiscalyearstatus;
        BEGIN
            IF TG_OP = 'INSERT'
               OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
               OR NEW.fiscal_year_id IS DISTINCT FROM OLD.fiscal_year_id THEN
                SELECT status INTO fiscal_year_status
                FROM public.fiscal_years
                WHERE id = NEW.fiscal_year_id
                  AND organization_id = NEW.organization_id
                FOR UPDATE;

                IF fiscal_year_status IS NULL THEN
                    RAISE EXCEPTION 'fiscal period organization must match fiscal year organization';
                END IF;
                IF fiscal_year_status <> 'OPEN' THEN
                    RAISE EXCEPTION 'fiscal periods can only be created in open fiscal years';
                END IF;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.fiscal_periods AS existing_period
                WHERE existing_period.organization_id = NEW.organization_id
                  AND existing_period.fiscal_year_id = NEW.fiscal_year_id
                  AND existing_period.id <> COALESCE(OLD.id, '')
                  AND NEW.start_date <= existing_period.end_date
                  AND NEW.end_date >= existing_period.start_date
            ) THEN
                RAISE EXCEPTION 'fiscal period dates overlap an existing fiscal period';
            END IF;

            IF TG_OP = 'INSERT' AND NEW.status <> 'OPEN' THEN
                RAISE EXCEPTION 'new fiscal periods must start OPEN';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF OLD.status = 'CLOSED' AND NEW.status IS DISTINCT FROM OLD.status THEN
                    RAISE EXCEPTION 'closed fiscal periods cannot be reopened';
                END IF;
                IF OLD.status = 'OPEN' AND NEW.status = 'CLOSED' THEN
                    RAISE EXCEPTION 'fiscal periods must be locked before closing';
                END IF;
                IF OLD.status = 'LOCKED' AND NEW.status = 'CLOSED' THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM public.period_closings
                        WHERE fiscal_period_id = OLD.id
                          AND organization_id = OLD.organization_id
                    ) THEN
                        RAISE EXCEPTION 'a period closing record is required before closing a fiscal period';
                    END IF;
                END IF;
                IF OLD.status = 'LOCKED'
                   AND NEW.status NOT IN ('LOCKED', 'CLOSED') THEN
                    RAISE EXCEPTION 'locked fiscal periods cannot change to the requested status';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_fiscal_periods_integrity
        BEFORE INSERT OR UPDATE ON fiscal_periods
        FOR EACH ROW EXECUTE FUNCTION enforce_fiscal_period_integrity();
        """
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
                RETURN NEW;
            END IF;

            IF OLD.status IN ('POSTED', 'VOIDED') THEN
                RAISE EXCEPTION 'posted or voided journal entries are immutable';
            END IF;

            IF OLD.status = 'DRAFT' AND NEW.status <> OLD.status THEN
                IF NEW.status <> 'POSTED' THEN
                    RAISE EXCEPTION 'draft journal entries can only transition to POSTED';
                END IF;
                IF current_user <> 'fip_accounting_owner' THEN
                    RAISE EXCEPTION 'journal entry posting must use the authorized accounting procedure';
                END IF;
                IF NEW.posted_at IS NULL THEN
                    RAISE EXCEPTION 'posted journal entries require posted_at';
                END IF;
                SELECT status INTO period_status
                FROM public.fiscal_periods
                WHERE id = NEW.fiscal_period_id
                  AND organization_id = NEW.organization_id;
                IF period_status <> 'OPEN' THEN
                    RAISE EXCEPTION 'journal entries can only be posted in open fiscal periods';
                END IF;
                SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                INTO line_count, debit_total, credit_total
                FROM public.journal_entry_lines
                WHERE journal_entry_id = NEW.id
                  AND organization_id = NEW.organization_id;
                IF line_count < 2 OR debit_total <> credit_total THEN
                    RAISE EXCEPTION 'posted journal entries must have balanced lines';
                END IF;
            END IF;

            IF NEW.status = 'DRAFT' AND NEW.posted_at IS NOT NULL THEN
                RAISE EXCEPTION 'draft journal entries cannot have posted_at';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entries_integrity
        BEFORE INSERT OR UPDATE OR DELETE ON journal_entries
        FOR EACH ROW EXECUTE FUNCTION enforce_journal_entry_integrity();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_journal_entry_line_integrity()
        RETURNS trigger AS $$
        DECLARE
            parent_status journalentrystatus;
        BEGIN
            SELECT status INTO parent_status
            FROM public.journal_entries
            WHERE id = COALESCE(NEW.journal_entry_id, OLD.journal_entry_id)
              AND organization_id = COALESCE(NEW.organization_id, OLD.organization_id);

            IF parent_status IN ('POSTED', 'VOIDED') THEN
                RAISE EXCEPTION 'lines of posted or voided journal entries are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_journal_entry_lines_integrity
        BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_lines
        FOR EACH ROW EXECUTE FUNCTION enforce_journal_entry_line_integrity();
        """
    )
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute(f"REVOKE CREATE ON SCHEMA public FROM {APPLICATION_ROLE}")
    op.execute(
        f"REVOKE CREATE ON DATABASE {op.get_bind().engine.url.database} FROM PUBLIC"
    )
    op.execute(
        f"REVOKE CREATE ON DATABASE {op.get_bind().engine.url.database} FROM {APPLICATION_ROLE}"
    )
    op.execute(f"REVOKE {DATABASE_OWNER_ROLE} FROM {APPLICATION_ROLE}")
    op.execute(f"REVOKE {ACCOUNTING_OWNER_ROLE} FROM {APPLICATION_ROLE}")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF (SELECT pg_get_userbyid(datdba)
                FROM pg_database
                WHERE datname = current_database()) = '{APPLICATION_ROLE}' THEN
                RAISE EXCEPTION 'application role must not own the database';
            END IF;
            IF has_database_privilege('{APPLICATION_ROLE}', current_database(), 'CREATE') THEN
                RAISE EXCEPTION 'application role must not have CREATE on the database';
            END IF;
            IF has_schema_privilege('{APPLICATION_ROLE}', 'public', 'CREATE') THEN
                RAISE EXCEPTION 'application role must not have CREATE on the public schema';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM pg_auth_members AS membership
                JOIN pg_roles AS member ON member.oid = membership.member
                JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
                WHERE member.rolname = '{APPLICATION_ROLE}'
                  AND granted_role.rolname IN (
                      '{DATABASE_OWNER_ROLE}', '{ACCOUNTING_OWNER_ROLE}'
                  )
            ) THEN
                RAISE EXCEPTION 'application role must not inherit privileged owner roles';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION post_journal_entry(target_entry_id text)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM public.accounting_security_credentials
                WHERE credential_key = 'posting'
                  AND secret_hash = encode(
                      digest(current_setting('fip.posting_token', true), 'sha256'),
                      'hex'
                  )
            ) THEN
                RAISE EXCEPTION 'journal entry posting authorization failed';
            END IF;

            UPDATE public.journal_entries
            SET status = 'POSTED', posted_at = CURRENT_TIMESTAMP
            WHERE id = target_entry_id AND status = 'DRAFT';

            IF NOT FOUND THEN
                RAISE EXCEPTION 'draft journal entry not found';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        f"ALTER FUNCTION post_journal_entry(text) OWNER TO {ACCOUNTING_OWNER_ROLE}"
    )

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APPLICATION_ROLE}"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APPLICATION_ROLE}"
    )
    for table_name in ("journal_entries", "journal_entry_lines"):
        op.execute(f"REVOKE ALL ON TABLE {table_name} FROM {APPLICATION_ROLE}")
        op.execute(f"GRANT SELECT, INSERT ON TABLE {table_name} TO {APPLICATION_ROLE}")
    for table_name in ("accounts", "fiscal_years", "fiscal_periods", "journals"):
        op.execute(f"REVOKE ALL ON TABLE {table_name} FROM {APPLICATION_ROLE}")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON TABLE {table_name} TO {APPLICATION_ROLE}"
        )
    op.execute(f"REVOKE ALL ON TABLE period_closings FROM {APPLICATION_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE period_closings TO {APPLICATION_ROLE}")
    op.execute(
        f"REVOKE ALL ON TABLE accounting_security_credentials FROM {APPLICATION_ROLE}"
    )
    op.execute("REVOKE ALL ON FUNCTION post_journal_entry(text) FROM PUBLIC")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION post_journal_entry(text) TO {APPLICATION_ROLE}"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS post_journal_entry(text)")
    op.execute(f"ALTER SCHEMA public OWNER TO {APPLICATION_ROLE}")
    op.execute(
        f"ALTER DATABASE {op.get_bind().engine.url.database} OWNER TO {APPLICATION_ROLE}"
    )
    op.execute("DROP TABLE IF EXISTS accounting_security_credentials")
    for table_name in (
        "accounts",
        "fiscal_years",
        "fiscal_periods",
        "journals",
        "journal_entries",
        "journal_entry_lines",
        "period_closings",
    ):
        op.execute(f"ALTER TABLE {table_name} OWNER TO {APPLICATION_ROLE}")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_entry_lines_integrity ON journal_entry_lines"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_journal_entry_line_integrity()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_journal_entries_integrity ON journal_entries"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_journal_entry_integrity()")
    op.execute("DROP TRIGGER IF EXISTS trg_fiscal_periods_integrity ON fiscal_periods")
    op.execute("DROP FUNCTION IF EXISTS enforce_fiscal_period_integrity()")
    op.drop_constraint(
        "fk_journal_entry_lines_organization_account",
        "journal_entry_lines",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_journal_entry_lines_organization_entry",
        "journal_entry_lines",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_journal_entries_organization_period",
        "journal_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_journal_entries_organization_journal",
        "journal_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_fiscal_periods_organization_year",
        "fiscal_periods",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_journal_entries_organization_id_id",
        "journal_entries",
        type_="unique",
    )
    for table_name in ("accounts", "fiscal_years", "fiscal_periods", "journals"):
        op.drop_constraint(
            f"uq_{table_name}_organization_id_id",
            table_name,
            type_="unique",
        )
    op.drop_index("ix_journal_entry_lines_organization_id", "journal_entry_lines")
    op.drop_column("journal_entry_lines", "organization_id")
