from sqlalchemy.dialects import postgresql

from app.models.accounting.balance_sheet_mapping import BalanceSheetAccountMapping


def test_balance_sheet_mapping_declares_postgresql_overlap_exclusion() -> None:
    constraints = BalanceSheetAccountMapping.__table__.constraints
    exclusion = next(
        constraint
        for constraint in constraints
        if constraint.name == "ex_balance_sheet_mapping_no_overlap"
    )

    assert isinstance(exclusion, postgresql.ExcludeConstraint)
    assert exclusion.name == "ex_balance_sheet_mapping_no_overlap"
    assert len(exclusion._render_exprs) == 4


def test_balance_sheet_mapping_overlap_exclusion_is_postgresql_only() -> None:
    exclusion = next(
        constraint
        for constraint in BalanceSheetAccountMapping.__table__.constraints
        if constraint.name == "ex_balance_sheet_mapping_no_overlap"
    )

    ddl = exclusion.ddl_if
    assert ddl is not None
