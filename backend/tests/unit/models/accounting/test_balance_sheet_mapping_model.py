from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

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


def test_balance_sheet_mapping_compiles_overlap_exclusion_for_postgresql() -> None:
    ddl = str(
        CreateTable(BalanceSheetAccountMapping.__table__).compile(
            dialect=postgresql.dialect()
        )
    )

    assert "EXCLUDE USING gist" in ddl
    assert "daterange(effective_from, effective_to, '[]')" in ddl
    assert "ex_balance_sheet_mapping_no_overlap" in ddl
