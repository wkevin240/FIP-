"""Create the initial FIP relational schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    fiscal_year_status = sa.Enum("OPEN", "CLOSED", name="fiscalyearstatus")
    fiscal_period_status = sa.Enum(
        "OPEN", "CLOSED", "LOCKED", name="fiscalperiodstatus"
    )
    journal_type = sa.Enum(
        "GENERAL",
        "SALES",
        "PURCHASES",
        "CASH",
        "BANK",
        "MISCELLANEOUS",
        name="journaltype",
    )
    journal_entry_status = sa.Enum(
        "DRAFT", "POSTED", "VOIDED", name="journalentrystatus"
    )

    op.create_table(
        "organizations",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=True)

    op.create_table(
        "users",
        *_base_columns(),
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
        *_base_columns(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)

    op.create_table(
        "permissions",
        *_base_columns(),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("permission_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "organization_memberships",
        *_base_columns(),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "organization_id", name="uq_membership_user_organization"
        ),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_memberships_user_id", "organization_memberships", ["user_id"]
    )

    op.create_table(
        "accounts",
        *_base_columns(),
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
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_account_organization_code"
        ),
    )
    op.create_index("ix_accounts_code", "accounts", ["code"])
    op.create_index("ix_accounts_organization_id", "accounts", ["organization_id"])

    op.create_table(
        "fiscal_years",
        *_base_columns(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("status", fiscal_year_status, nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_fiscal_year_dates"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "name", name="uq_fiscal_year_organization_name"
        ),
    )
    op.create_index("ix_fiscal_years_name", "fiscal_years", ["name"])
    op.create_index(
        "ix_fiscal_years_organization_id", "fiscal_years", ["organization_id"]
    )

    op.create_table(
        "fiscal_periods",
        *_base_columns(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", fiscal_period_status, nullable=False),
        sa.Column("fiscal_year_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_fiscal_period_dates"),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "fiscal_year_id",
            "name",
            name="uq_fiscal_period_organization_year_name",
        ),
    )
    op.create_index(
        "ix_fiscal_periods_organization_id", "fiscal_periods", ["organization_id"]
    )

    op.create_table(
        "journals",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("journal_type", journal_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_journal_organization_code"
        ),
    )
    op.create_index("ix_journals_organization_id", "journals", ["organization_id"])

    op.create_table(
        "journal_entries",
        *_base_columns(),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("journal_id", sa.String(), nullable=False),
        sa.Column("fiscal_period_id", sa.String(), nullable=False),
        sa.Column("entry_number", sa.String(length=50), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("status", journal_entry_status, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"], ["fiscal_periods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["journal_id"], ["journals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "journal_id",
            "entry_number",
            name="uq_journal_entry_organization_journal_number",
        ),
    )
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index(
        "ix_journal_entries_fiscal_period_id", "journal_entries", ["fiscal_period_id"]
    )
    op.create_index("ix_journal_entries_journal_id", "journal_entries", ["journal_id"])
    op.create_index(
        "ix_journal_entries_organization_id", "journal_entries", ["organization_id"]
    )
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])

    op.create_table(
        "journal_entry_lines",
        *_base_columns(),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("credit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "credit >= 0", name="ck_journal_entry_line_credit_non_negative"
        ),
        sa.CheckConstraint(
            "debit >= 0", name="ck_journal_entry_line_debit_non_negative"
        ),
        sa.CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_journal_entry_line_single_side_amount",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journal_entry_id", "line_number", name="uq_journal_entry_line_number"
        ),
    )
    op.create_index(
        "ix_journal_entry_lines_account_id", "journal_entry_lines", ["account_id"]
    )
    op.create_index(
        "ix_journal_entry_lines_journal_entry_id",
        "journal_entry_lines",
        ["journal_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_journal_entry_lines_journal_entry_id", table_name="journal_entry_lines"
    )
    op.drop_index("ix_journal_entry_lines_account_id", table_name="journal_entry_lines")
    op.drop_table("journal_entry_lines")
    op.drop_index("ix_journal_entries_status", table_name="journal_entries")
    op.drop_index("ix_journal_entries_organization_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_journal_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_fiscal_period_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_entry_date", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_journals_organization_id", table_name="journals")
    op.drop_table("journals")
    op.drop_index("ix_fiscal_periods_organization_id", table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
    op.drop_index("ix_fiscal_years_organization_id", table_name="fiscal_years")
    op.drop_index("ix_fiscal_years_name", table_name="fiscal_years")
    op.drop_table("fiscal_years")
    op.drop_index("ix_accounts_organization_id", table_name="accounts")
    op.drop_index("ix_accounts_code", table_name="accounts")
    op.drop_table("accounts")
    op.drop_index(
        "ix_organization_memberships_user_id", table_name="organization_memberships"
    )
    op.drop_index(
        "ix_organization_memberships_organization_id",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")
    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_table("organizations")

    bind = op.get_bind()
    sa.Enum("DRAFT", "POSTED", "VOIDED", name="journalentrystatus").drop(
        bind, checkfirst=True
    )
    sa.Enum(
        "GENERAL",
        "SALES",
        "PURCHASES",
        "CASH",
        "BANK",
        "MISCELLANEOUS",
        name="journaltype",
    ).drop(bind, checkfirst=True)
    sa.Enum("OPEN", "CLOSED", "LOCKED", name="fiscalperiodstatus").drop(
        bind, checkfirst=True
    )
    sa.Enum("OPEN", "CLOSED", name="fiscalyearstatus").drop(bind, checkfirst=True)
