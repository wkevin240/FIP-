from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.db.base import Base


class Scenario(Base):
    __tablename__ = "fpa_scenarios"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_fpa_scenario_org_id"),
        UniqueConstraint(
            "organization_id",
            "fiscal_year_id",
            "code",
            name="uq_fpa_scenario_org_year_code",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'LOCKED')", name="ck_fpa_scenario_status"
        ),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_year_id"],
            ["fiscal_years.organization_id", "fiscal_years.id"],
            name="fk_fpa_scenario_org_year",
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
    code = Column(String(64), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="DRAFT", index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class ScenarioAssumption(Base):
    __tablename__ = "fpa_scenario_assumptions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "scenario_id",
            "fiscal_period_id",
            "account_id",
            "dimension_value_id",
            name="uq_fpa_assumption_scope",
        ),
        Index(
            "uq_fpa_assumption_scope_without_dimension",
            "organization_id",
            "scenario_id",
            "fiscal_period_id",
            "account_id",
            unique=True,
            postgresql_where=Column("dimension_value_id").is_(None),
        ),
        UniqueConstraint("organization_id", "id", name="uq_fpa_assumption_org_id"),
        CheckConstraint("amount <> 0", name="ck_fpa_assumption_non_zero"),
        ForeignKeyConstraint(
            ["organization_id", "scenario_id"],
            ["fpa_scenarios.organization_id", "fpa_scenarios.id"],
            name="fk_fpa_assumption_org_scenario",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "fiscal_period_id"],
            ["fiscal_periods.organization_id", "fiscal_periods.id"],
            name="fk_fpa_assumption_org_period",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "account_id"],
            ["accounts.organization_id", "accounts.id"],
            name="fk_fpa_assumption_org_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "dimension_value_id"],
            [
                "analytical_dimension_values.organization_id",
                "analytical_dimension_values.id",
            ],
            name="fk_fpa_assumption_org_dimension_value",
            ondelete="RESTRICT",
        ),
    )

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scenario_id = Column(String, nullable=False, index=True)
    fiscal_period_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=False, index=True)
    dimension_value_id = Column(String, nullable=True, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    rationale = Column(Text, nullable=False)
    created_by_user_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
