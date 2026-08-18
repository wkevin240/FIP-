from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class BankingControlException(Base):
    __tablename__ = "banking_control_exceptions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "bank_transaction_id",
            name="uq_banking_control_exception_org_transaction",
        ),
        ForeignKeyConstraint(
            ["organization_id", "bank_transaction_id"],
            ["bank_transactions.organization_id", "bank_transactions.id"],
            name="fk_banking_control_exception_org_transaction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_banking_control_exception_org_import",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('NO_MATCH', 'AMBIGUOUS', 'PENDING', 'REJECTED', 'INVALID_RULE', 'POSTED_UNRECONCILED', 'RECONCILED')",
            name="ck_banking_control_exception_status",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_transaction_id = Column(String, nullable=False, index=True)
    statement_import_id = Column(String, nullable=True, index=True)
    status = Column(String(32), nullable=False, index=True)
    reason = Column(String(500), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class BankStatementClosure(Base):
    __tablename__ = "bank_statement_closures"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "statement_import_id",
            name="uq_bank_statement_closure_org_import",
        ),
        ForeignKeyConstraint(
            ["organization_id", "statement_import_id"],
            ["bank_statement_imports.organization_id", "bank_statement_imports.id"],
            name="fk_bank_statement_closure_org_import",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "unresolved_count = 0", name="ck_bank_statement_closure_no_unresolved"
        ),
        CheckConstraint(
            "imported_count >= 0 AND reconciled_count >= 0",
            name="ck_bank_statement_closure_counts_non_negative",
        ),
        CheckConstraint(
            "reconciled_count <= imported_count",
            name="ck_bank_statement_closure_reconciled_bound",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    statement_import_id = Column(String, nullable=False)
    closed_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    closed_at = Column(DateTime(timezone=True), nullable=False)
    imported_count = Column(Integer, nullable=False)
    reconciled_count = Column(Integer, nullable=False)
    unresolved_count = Column(Integer, nullable=False)
