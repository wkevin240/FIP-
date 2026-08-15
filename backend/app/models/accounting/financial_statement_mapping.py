from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class FinancialStatementMapping(Base):
    """Tenant-scoped presentation mapping for professional financial statements."""

    __tablename__ = "financial_statement_mappings"
    __table_args__ = (
        CheckConstraint(
            "framework IN ('SYSCOHADA')", name="ck_financial_mapping_framework"
        ),
        CheckConstraint(
            "statement_code IN ('BALANCE_SHEET', 'INCOME_STATEMENT')",
            name="ck_financial_mapping_statement_code",
        ),
        CheckConstraint(
            "(statement_code = 'BALANCE_SHEET' AND presentation_role IN ('ASSETS', 'LIABILITIES_EQUITY')) "
            "OR (statement_code = 'INCOME_STATEMENT' AND presentation_role IN ('REVENUE', 'EXPENSE'))",
            name="ck_financial_mapping_presentation_role",
        ),
        CheckConstraint(
            "line_code <> ''", name="ck_financial_mapping_line_code_not_empty"
        ),
        CheckConstraint(
            "line_label <> ''", name="ck_financial_mapping_line_label_not_empty"
        ),
        CheckConstraint(
            "section_code <> ''", name="ck_financial_mapping_section_code_not_empty"
        ),
        CheckConstraint(
            "display_order >= 0", name="ck_financial_mapping_display_order"
        ),
        UniqueConstraint(
            "organization_id",
            "account_id",
            "framework",
            "statement_code",
            name="uq_financial_mapping_organization_account_statement",
        ),
        UniqueConstraint(
            "organization_id",
            "framework",
            "statement_code",
            "line_code",
            "account_id",
            name="uq_financial_mapping_organization_line_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_financial_mapping_organization_account",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id = Column(String, nullable=False, index=True)
    framework = Column(String(32), nullable=False, default="SYSCOHADA")
    statement_code = Column(String(32), nullable=False)
    presentation_role = Column(String(32), nullable=False)
    section_code = Column(String(64), nullable=False)
    section_label = Column(String(255), nullable=False)
    line_code = Column(String(64), nullable=False)
    line_label = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
