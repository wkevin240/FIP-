from datetime import date
from decimal import Decimal

from app.domain.accounting.reporting.rules import FinancialReportingRules
from app.repositories.accounting.reporting_repository import ReportingRepository
from app.schemas.accounting.reporting import (
    BalanceSheetResponse,
    ComparativeBalanceLine,
    ComparativeBalanceResponse,
    FinancialStatementLine,
    GeneralLedgerLine,
    GeneralLedgerResponse,
    IncomeStatementResponse,
    TrialBalanceLine,
    TrialBalanceResponse,
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
        total_assets = total_liabilities = total_equity = current_earnings = Decimal(
            "0.00"
        )
        for account, debit, credit in movements:
            balance = FinancialReportingRules.balance_for_account(
                account.account_type, debit, credit
            )
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
        FinancialReportingRules.validate_balance_sheet(
            total_assets, total_liabilities + total_equity + current_earnings
        )
        return BalanceSheetResponse(
            as_of_date=as_of_date,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            current_earnings=current_earnings,
            total_liabilities_and_equity=total_liabilities
            + total_equity
            + current_earnings,
            is_balanced=True,
        )

    async def income_statement(
        self, organization_id: str, start_date: date, end_date: date
    ) -> IncomeStatementResponse:
        self._validate_range(start_date, end_date)
        movements = await self.repository.account_movements(
            organization_id, start_date, end_date
        )
        revenues: list[FinancialStatementLine] = []
        expenses: list[FinancialStatementLine] = []
        total_revenue = total_expenses = Decimal("0.00")
        for account, debit, credit in movements:
            if (
                account.account_type
                not in FinancialReportingRules.INCOME_STATEMENT_TYPES
            ):
                continue
            balance = FinancialReportingRules.balance_for_account(
                account.account_type, debit, credit
            )
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

    async def trial_balance(
        self, organization_id: str, end_date: date, start_date: date | None = None
    ) -> TrialBalanceResponse:
        if start_date:
            self._validate_range(start_date, end_date)
        lines: list[TrialBalanceLine] = []
        total_debit = total_credit = Decimal("0.00")
        for account, debit, credit in await self.repository.account_movements(
            organization_id, start_date, end_date
        ):
            total_debit += debit
            total_credit += credit
            lines.append(
                TrialBalanceLine(
                    account_id=account.id,
                    code=account.code,
                    name=account.name,
                    account_type=account.account_type,
                    debit=debit,
                    credit=credit,
                    balance=FinancialReportingRules.balance_for_account(
                        account.account_type, debit, credit
                    ),
                )
            )
        return TrialBalanceResponse(
            start_date=start_date,
            end_date=end_date,
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=total_debit == total_credit,
        )

    async def general_ledger(
        self,
        organization_id: str,
        account_id: str,
        start_date: date | None,
        end_date: date | None,
        skip: int,
        limit: int,
    ) -> GeneralLedgerResponse:
        if start_date and end_date:
            self._validate_range(start_date, end_date)
        running = await self.repository.ledger_opening_balance(
            organization_id, account_id, start_date, skip
        )
        lines: list[GeneralLedgerLine] = []
        for entry, line in await self.repository.ledger_lines(
            organization_id, account_id, start_date, end_date, skip, limit
        ):
            running += Decimal(line.debit) - Decimal(line.credit)
            lines.append(
                GeneralLedgerLine(
                    journal_entry_id=entry.id,
                    entry_number=entry.entry_number,
                    entry_date=entry.entry_date,
                    line_number=line.line_number,
                    description=entry.description,
                    debit=Decimal(line.debit),
                    credit=Decimal(line.credit),
                    running_balance=running,
                )
            )
        return GeneralLedgerResponse(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
            lines=lines,
        )

    async def comparative_balance(
        self,
        organization_id: str,
        current_start_date: date,
        current_end_date: date,
        previous_start_date: date,
        previous_end_date: date,
    ) -> ComparativeBalanceResponse:
        self._validate_range(current_start_date, current_end_date)
        self._validate_range(previous_start_date, previous_end_date)
        current = {
            a.id: (a, d, c)
            for a, d, c in await self.repository.account_movements(
                organization_id, current_start_date, current_end_date
            )
        }
        previous = {
            a.id: (a, d, c)
            for a, d, c in await self.repository.account_movements(
                organization_id, previous_start_date, previous_end_date
            )
        }
        ytd = {
            a.id: (a, d, c)
            for a, d, c in await self.repository.account_movements(
                organization_id, end_date=current_end_date
            )
        }
        lines = []
        for account_id in sorted(
            set(current) | set(previous) | set(ytd),
            key=lambda item: (
                (current.get(item) or previous.get(item) or ytd[item])[0].code
            ),
        ):
            account = (
                current.get(account_id) or previous.get(account_id) or ytd[account_id]
            )[0]

            def balance(
                values: tuple | None, account_type: str = account.account_type
            ) -> Decimal:
                return (
                    Decimal("0.00")
                    if values is None
                    else FinancialReportingRules.balance_for_account(
                        account_type, values[1], values[2]
                    )
                )

            lines.append(
                ComparativeBalanceLine(
                    account_id=account.id,
                    code=account.code,
                    name=account.name,
                    current_balance=balance(current.get(account_id)),
                    previous_balance=balance(previous.get(account_id)),
                    year_to_date_balance=balance(ytd.get(account_id)),
                )
            )
        return ComparativeBalanceResponse(
            current_start_date=current_start_date,
            current_end_date=current_end_date,
            previous_start_date=previous_start_date,
            previous_end_date=previous_end_date,
            lines=lines,
        )

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )
