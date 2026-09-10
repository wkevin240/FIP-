"""Initial persistence schema for the FIP financial kernel.

Revision ID: 20260910_0001
Revises: None
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    fiscal_year_status = sa.Enum("OPEN", "CLOSED", name="fiscalyearstatus")
    fiscal_period_status = sa.Enum("OPEN", "CLOSING", "CLOSED", "LOCKED", name="fiscalperiodstatus")
    journal_entry_status = sa.Enum("DRAFT", "POSTED", "REVERSED", name="journalentrystatus")

    bind = op.get_bind()
    fiscal_year_status.create(bind, checkfirst=True)
    fiscal_period_status.create(bind, checkfirst=True)
    journal_entry_status.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_organization"),
    )
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
    op.create_index("ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("permission_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("account_type", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("collective_account_id", sa.String(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["collective_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_account_organization_code"),
    )
    op.create_index("ix_accounts_organization_id", "accounts", ["organization_id"])
    op.create_index("ix_accounts_code", "accounts", ["code"])

    op.create_table(
        "fiscal_years",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("status", fiscal_year_status, nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_fiscal_year_dates"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_fiscal_year_organization_name"),
    )
    op.create_index("ix_fiscal_years_name", "fiscal_years", ["name"])
    op.create_index("ix_fiscal_years_organization_id", "fiscal_years", ["organization_id"])

    op.create_table(
        "fiscal_periods",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", fiscal_period_status, nullable=False),
        sa.Column("fiscal_year_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_fiscal_period_dates"),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "fiscal_year_id", "name", name="uq_fiscal_period_organization_year_name"),
    )
    op.create_index("ix_fiscal_periods_organization_id", "fiscal_periods", ["organization_id"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", journal_entry_status, nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("idempotency_hash", sa.String(length=64), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by", sa.String(), nullable=True),
        sa.Column("reversal_of_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_journal_entry_org_idempotency"),
        sa.UniqueConstraint("reversal_of_id", name="uq_journal_entry_reversal_of"),
    )
    op.create_index("ix_journal_entries_organization_id", "journal_entries", ["organization_id"])
    op.create_index("ix_journal_entries_fiscal_period_id", "journal_entries", ["fiscal_period_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])
    op.create_index("ix_journal_entries_reversal_of_id", "journal_entries", ["reversal_of_id"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("debit", sa.Numeric(20, 2), nullable=False),
        sa.Column("credit", sa.Numeric(20, 2), nullable=False),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_entry_line_non_negative"),
        sa.CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="ck_journal_entry_line_one_side"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_entry_line_number"),
    )
    op.create_index("ix_journal_entry_lines_journal_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_index("ix_journal_entry_lines_account_id", "journal_entry_lines", ["account_id"])

    op.create_table(
        "ledger_postings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("journal_entry_line_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("debit", sa.Numeric(20, 2), nullable=False),
        sa.Column("credit", sa.Numeric(20, 2), nullable=False),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_posting_non_negative"),
        sa.CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="ck_ledger_posting_one_side"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["journal_entry_line_id"], ["journal_entry_lines.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id", "journal_entry_line_id", name="uq_ledger_posting_source_line"),
    )
    op.create_index("ix_ledger_postings_organization_id", "ledger_postings", ["organization_id"])
    op.create_index("ix_ledger_postings_fiscal_period_id", "ledger_postings", ["fiscal_period_id"])
    op.create_index("ix_ledger_postings_journal_entry_id", "ledger_postings", ["journal_entry_id"])
    op.create_index("ix_ledger_postings_journal_entry_line_id", "ledger_postings", ["journal_entry_line_id"])
    op.create_index("ix_ledger_postings_account_id", "ledger_postings", ["account_id"])
    op.create_index("ix_ledger_postings_posting_date", "ledger_postings", ["posting_date"])


def downgrade() -> None:
    op.drop_table("ledger_postings")
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("fiscal_periods")
    op.drop_table("fiscal_years")
    op.drop_table("accounts")
    op.drop_table("role_permissions")
    op.drop_table("organization_memberships")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("organizations")

    bind = op.get_bind()
    sa.Enum(name="journalentrystatus").drop(bind, checkfirst=True)
    sa.Enum(name="fiscalperiodstatus").drop(bind, checkfirst=True)
    sa.Enum(name="fiscalyearstatus").drop(bind, checkfirst=True)
