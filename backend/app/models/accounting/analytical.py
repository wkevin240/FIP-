from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)

from app.db.base import Base


class AnalyticalDimension(Base):
    __tablename__ = "analytical_dimensions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_analytical_dimension_org_id"
        ),
        UniqueConstraint(
            "organization_id", "code", name="uq_analytical_dimension_org_code"
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(64), nullable=False)
    name = Column(String(120), nullable=False)
    is_active = Column(String(5), nullable=False, default="true")


class AnalyticalDimensionValue(Base):
    __tablename__ = "analytical_dimension_values"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_analytical_value_org_id"),
        UniqueConstraint(
            "organization_id",
            "dimension_id",
            "code",
            name="uq_analytical_value_org_dimension_code",
        ),
        ForeignKeyConstraint(
            ["organization_id", "dimension_id"],
            ["analytical_dimensions.organization_id", "analytical_dimensions.id"],
            name="fk_analytical_value_org_dimension",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dimension_id = Column(String, nullable=False, index=True)
    code = Column(String(64), nullable=False)
    label = Column(String(120), nullable=False)
    is_active = Column(String(5), nullable=False, default="true")


class JournalEntryLineAnalyticAllocation(Base):
    __tablename__ = "journal_entry_line_analytic_allocations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_analytic_allocation_org_id"),
        UniqueConstraint(
            "organization_id",
            "journal_entry_line_id",
            "dimension_id",
            "dimension_value_id",
            name="uq_analytic_allocation_line_dimension_value",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_analytic_allocation_org_idempotency",
        ),
        CheckConstraint("amount > 0", name="ck_analytic_allocation_positive_amount"),
        ForeignKeyConstraint(
            ["organization_id", "journal_entry_line_id"],
            ["journal_entry_lines.organization_id", "journal_entry_lines.id"],
            name="fk_analytic_allocation_org_line",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "dimension_id"],
            ["analytical_dimensions.organization_id", "analytical_dimensions.id"],
            name="fk_analytic_allocation_org_dimension",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "dimension_id", "dimension_value_id"],
            [
                "analytical_dimension_values.organization_id",
                "analytical_dimension_values.dimension_id",
                "analytical_dimension_values.id",
            ],
            name="fk_analytic_allocation_org_dimension_value",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    journal_entry_line_id = Column(String, nullable=False, index=True)
    dimension_id = Column(String, nullable=False, index=True)
    dimension_value_id = Column(String, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
