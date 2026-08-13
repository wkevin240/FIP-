from decimal import Decimal


class FinancialReportingRules:
    BALANCE_SHEET_TYPES = frozenset({"ASSET", "LIABILITY", "EQUITY"})
    INCOME_STATEMENT_TYPES = frozenset({"REVENUE", "EXPENSE"})

    @staticmethod
    def balance_for_account(
        account_type: str, debit: Decimal, credit: Decimal
    ) -> Decimal:
        if account_type in {"ASSET", "EXPENSE"}:
            return debit - credit
        if account_type in {"LIABILITY", "EQUITY", "REVENUE"}:
            return credit - debit
        raise ValueError(f"Unsupported account type: {account_type}")

    @staticmethod
    def validate_balance_sheet(
        total_assets: Decimal, total_liabilities_and_equity: Decimal
    ) -> None:
        if total_assets != total_liabilities_and_equity:
            raise ValueError("Balance sheet assets must equal liabilities and equity")
