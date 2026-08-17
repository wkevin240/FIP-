"""Add credit note and payment accounting postings.

Revision ID: 0019_invoice_settlement
Revises: 0018_treasury_accounting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_invoice_settlement"
down_revision: str | None = "0018_treasury_accounting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _secure(table: str) -> None:
    op.execute(f"ALTER TABLE {table} OWNER TO fip_accounting_owner")
    op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO fip_user")


def _posting_table(
    name: str, source_table: str, source_type: str, extra: list[sa.Column] | None = None
) -> None:
    columns = [
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("source_module", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("journal_entry_id", sa.String(), nullable=False),
        *(extra or []),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_id"],
            [f"{source_table}.organization_id", f"{source_table}.id"],
            name=f"fk_{name}_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "journal_entry_id"],
            ["journal_entries.organization_id", "journal_entries.id"],
            name=f"fk_{name}_entry",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("source_module = 'INVOICING'", name=f"ck_{name}_module"),
        sa.CheckConstraint(f"source_type = '{source_type}'", name=f"ck_{name}_type"),
        sa.CheckConstraint("status = 'POSTED'", name=f"ck_{name}_status"),
        sa.UniqueConstraint("organization_id", "source_id", name=f"uq_{name}_source"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name=f"uq_{name}_key"
        ),
        sa.UniqueConstraint(
            "organization_id", "journal_entry_id", name=f"uq_{name}_entry"
        ),
    ]
    op.create_table(name, *columns)
    _secure(name)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM public.credit_notes) THEN
            RAISE EXCEPTION 'Credit note HT/TVA breakdown is required before migration 0019';
          END IF;
        END $$;
        """
    )
    op.add_column(
        "credit_notes", sa.Column("subtotal", sa.Numeric(18, 2), nullable=False)
    )
    op.add_column(
        "credit_notes", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False)
    )
    op.create_check_constraint(
        "ck_credit_note_amount_breakdown",
        "credit_notes",
        "subtotal >= 0 AND tax_amount >= 0 AND amount = subtotal + tax_amount",
    )
    op.create_unique_constraint(
        "uq_credit_notes_organization_id_id",
        "credit_notes",
        ["organization_id", "id"],
    )
    op.create_unique_constraint(
        "uq_payments_organization_id_id",
        "payments",
        ["organization_id", "id"],
    )
    _posting_table("credit_note_accounting_postings", "credit_notes", "CREDIT_NOTE")
    _posting_table(
        "payment_accounting_postings",
        "payments",
        "PAYMENT",
        [sa.Column("settlement_account_id", sa.String(), nullable=False)],
    )
    op.create_foreign_key(
        "fk_pay_acc_settlement",
        "payment_accounting_postings",
        "accounts",
        ["organization_id", "settlement_account_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_table("payment_accounting_postings")
    op.drop_table("credit_note_accounting_postings")
    op.execute(
        "ALTER TABLE public.payments DROP CONSTRAINT IF EXISTS uq_payments_organization_id_id"
    )
    op.execute(
        "ALTER TABLE public.credit_notes DROP CONSTRAINT IF EXISTS ck_credit_note_amount_breakdown"
    )
    op.execute("ALTER TABLE public.credit_notes DROP COLUMN IF EXISTS tax_amount")
    op.execute("ALTER TABLE public.credit_notes DROP COLUMN IF EXISTS subtotal")
    op.execute(
        "ALTER TABLE public.credit_notes DROP CONSTRAINT IF EXISTS uq_credit_notes_organization_id_id"
    )
