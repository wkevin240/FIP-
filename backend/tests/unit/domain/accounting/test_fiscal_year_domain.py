import pytest
from datetime import date
from app.domain.accounting.fiscal_year.rules import FiscalYearRules, FiscalPeriodRules

def test_fiscal_year_valid_dates():
    # Should not raise exception
    FiscalYearRules.validate_dates(date(2025, 1, 1), date(2025, 12, 31))

def test_fiscal_year_invalid_dates():
    with pytest.raises(ValueError, match="strictly after"):
        FiscalYearRules.validate_dates(date(2025, 12, 31), date(2025, 1, 1))

def test_fiscal_year_overlap():
    existing = [
        {"name": "2024", "start_date": date(2024, 1, 1), "end_date": date(2024, 12, 31)}
    ]
    with pytest.raises(ValueError, match="overlap"):
        FiscalYearRules.check_overlap(date(2024, 6, 1), date(2025, 5, 31), existing)

def test_fiscal_period_within_year():
    # Valid
    FiscalPeriodRules.validate_within_year(
        date(2025, 1, 1), date(2025, 1, 31),
        date(2025, 1, 1), date(2025, 12, 31)
    )
    
def test_fiscal_period_outside_year():
    # Invalid
    with pytest.raises(ValueError, match="within the fiscal year"):
        FiscalPeriodRules.validate_within_year(
            date(2024, 12, 1), date(2024, 12, 31),
            date(2025, 1, 1), date(2025, 12, 31)
        )
