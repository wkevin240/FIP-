from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class BankStatementImport(Base):
    """A tenant-scoped, idempotent CSV bank statement import batch."""

    __tablename__ = "bank_statement_imports"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_bank_statement_imports_org_id"
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_bank_statement_imports_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "treasury_bank_account_id"],
            ["treasury_bank_accounts.organization_id", "treasury_bank_accounts.id"],
            name="fk_bank_statement_imports_org_treasury_account",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "row_count > 0", name="ck_bank_statement_imports_positive_rows"
        ),
        CheckConstraint(
            "imported_count >= 0 AND duplicate_count >= 0",
            name="ck_bank_statement_imports_non_negative_counts",
        ),
        CheckConstraint(
            "imported_count + duplicate_count = row_count",
            name="ck_bank_statement_imports_count_reconciliation",
        ),
    )

    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    treasury_bank_account_id = Column(String, nullable=False)
    imported_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key = Column(String(128), nullable=False)
    content_hash = Column(String(64), nullable=False)
    source_filename = Column(String(255), nullable=False)
    format_version = Column(String(32), nullable=False, default="CSV_V1")
    row_count = Column(Integer, nullable=False)
    imported_count = Column(Integer, nullable=False)
    duplicate_count = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="COMPLETED")

    organization = relationship("Organization", overlaps="treasury_bank_account,lines")
    treasury_bank_account = relationship("TreasuryBankAccount", overlaps="organization")
    imported_by = relationship("User")
    lines = relationship(
        "BankStatementImportLine",
        back_populates="statement_import",
        cascade="all, delete-orphan",
        order_by="BankStatementImportLine.line_number",
        overlaps="organization,statement_import,bank_transaction",
    )


class BankStatementImportLine(Base):
    """Audit line linking an imported source row to its canonical transaction."""

    __tablename__ = "bank_statement_import_lines"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "statement_import_id",
            "line_number",
            name="uq_bank_statement_import_lines_number",
        ),
        UniqueConstraint(
            "organization_id",
            "statement_import_id",
            "external_id",
            name="uq_bank_statement_import_lines_external",
        ),
        ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_bank_statement_import_lines_org_import",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_bank_statement_import_lines_org_transaction",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('IMPORTED', 'DUPLICATE')",
            name="ck_bank_statement_import_lines_status",
        ),
    )

    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    statement_import_id = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    external_id = Column(String(100), nullable=False)
    bank_transaction_id = Column(String, nullable=False)
    row_hash = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)

    organization = relationship(
        "Organization", overlaps="lines,statement_import,bank_transaction"
    )
    statement_import = relationship(
        "BankStatementImport", back_populates="lines", overlaps="organization"
    )
    bank_transaction = relationship(
        "BankTransaction", overlaps="lines,organization,statement_import"
    )
