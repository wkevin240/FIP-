from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_budgets_organization_id_id"),
        UniqueConstraint("organization_id", "name", name="uq_budget_organization_name"),
        CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'LOCKED')", name="ck_budget_status"
        ),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_budget_organization_year",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_year_id = Column(String, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT", index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class BudgetLine(Base):
    __tablename__ = "budget_lines"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "budget_id",
            "fiscal_period_id",
            "account_id",
            name="uq_budget_line_org_budget_period_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "budget_id"],
            ["budgets.organization_id", "budgets.id"],
            name="fk_budget_line_organization_budget",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_period_id"],
            ["fiscal_periods.organization_id", "fiscal_periods.id"],
            name="fk_budget_line_organization_period",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_budget_line_organization_account",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    budget_id = Column(String, nullable=False, index=True)
    fiscal_period_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
