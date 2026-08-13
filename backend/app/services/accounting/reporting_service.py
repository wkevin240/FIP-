from datetime import date
from decimal import Decimal

from app.domain.accounting.reporting.rules import FinancialReportingRules
from app.repositories.accounting.reporting_repository import ReportingRepository
from app.schemas.accounting.reporting import (
    BalanceSheetResponse,
    FinancialStatementLine,
    IncomeStatementResponse,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class ReportingService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ReportingRepository(session)

    async def balance_sheet(
        self, organization_id: str, as_of_date: date
    ) -> BalanceSheetResponse:
        movements = await self.repository.account_movements(
            organization_id, end_date=as_of_date
        )
        assets: list[FinancialStatementLine] = []
        liabilities: list[FinancialStatementLine] = []
        equity: list[FinancialStatementLine] = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")
        current_earnings = Decimal("0.00")

        for account, debit, credit in movements:
            try:
                balance = FinancialReportingRules.balance_for_account(
                    account.account_type, debit, credit
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                ) from exc

            line = FinancialStatementLine(
                account_id=account.id,
                code=account.code,
                name=account.name,
                account_type=account.account_type,
                balance=balance,
            )
            if account.account_type == "ASSET":
                assets.append(line)
                total_assets += balance
            elif account.account_type == "LIABILITY":
                liabilities.append(line)
                total_liabilities += balance
            elif account.account_type == "EQUITY":
                equity.append(line)
                total_equity += balance
            elif account.account_type == "REVENUE":
                current_earnings += balance
            elif account.account_type == "EXPENSE":
                current_earnings -= balance

        total_liabilities_and_equity = (
            total_liabilities + total_equity + current_earnings
        )
        try:
            FinancialReportingRules.validate_balance_sheet(
                total_assets, total_liabilities_and_equity
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

        return BalanceSheetResponse(
            as_of_date=as_of_date,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            current_earnings=current_earnings,
            total_liabilities_and_equity=total_liabilities_and_equity,
            is_balanced=True,
        )

    async def income_statement(
        self, organization_id: str, start_date: date, end_date: date
    ) -> IncomeStatementResponse:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )

        movements = await self.repository.account_movements(
            organization_id, start_date=start_date, end_date=end_date
        )
        revenues: list[FinancialStatementLine] = []
        expenses: list[FinancialStatementLine] = []
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for account, debit, credit in movements:
            if (
                account.account_type
                not in FinancialReportingRules.INCOME_STATEMENT_TYPES
            ):
                continue
            try:
                balance = FinancialReportingRules.balance_for_account(
                    account.account_type, debit, credit
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                ) from exc

            line = FinancialStatementLine(
                account_id=account.id,
                code=account.code,
                name=account.name,
                account_type=account.account_type,
                balance=balance,
            )
            if account.account_type == "REVENUE":
                revenues.append(line)
                total_revenue += balance
            else:
                expenses.append(line)
                total_expenses += balance

        return IncomeStatementResponse(
            start_date=start_date,
            end_date=end_date,
            revenues=revenues,
            expenses=expenses,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_income=total_revenue - total_expenses,
        )
