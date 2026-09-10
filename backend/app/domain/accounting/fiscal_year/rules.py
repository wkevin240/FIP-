from datetime import date
from typing import List

from app.core.enums.accounting import FiscalPeriodStatus


class FiscalYearRules:
    @staticmethod
    def validate_dates(start_date: date, end_date: date):
        if end_date <= start_date:
            raise ValueError("End date must be strictly after start date")

    @staticmethod
    def check_overlap(start_date: date, end_date: date, existing_years: List[dict]):
        for year in existing_years:
            if start_date <= year["end_date"] and end_date >= year["start_date"]:
                raise ValueError(f"Fiscal year dates overlap with an existing fiscal year: {year['name']}")

    @staticmethod
    def validate_periods_closed(period_statuses: List[FiscalPeriodStatus]) -> None:
        if not period_statuses:
            raise ValueError("Fiscal year cannot be closed without fiscal periods")
        if any(status != FiscalPeriodStatus.CLOSED for status in period_statuses):
            raise ValueError("All fiscal periods must be closed before closing the fiscal year")


class FiscalPeriodRules:
    @staticmethod
    def validate_within_year(period_start: date, period_end: date, year_start: date, year_end: date):
        if period_start < year_start or period_end > year_end:
            raise ValueError("Fiscal period dates must be within the fiscal year dates")

    @staticmethod
    def validate_dates(start_date: date, end_date: date):
        if end_date <= start_date:
            raise ValueError("End date must be strictly after start date")
