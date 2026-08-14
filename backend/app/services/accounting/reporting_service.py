import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from app.domain.accounting.reporting.rules import FinancialReportingRules
from app.repositories.accounting.financial_statement_mapping_repository import (
    FinancialStatementMappingRepository,
)
from app.repositories.accounting.reporting_repository import ReportingRepository
from app.schemas.accounting.professional_reporting import (
    ProfessionalFinancialStatementLine,
    ProfessionalFinancialStatementResponse,
    ProfessionalTrialBalanceLine,
    ProfessionalTrialBalanceResponse,
    ReportingReconciliationResponse,
)
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
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class ReportingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ReportingRepository(session)
        self.mappings = FinancialStatementMappingRepository(session)
        self.audit = AuditService(session)

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

    async def professional_trial_balance(
        self, organization_id: str, start_date: date, end_date: date
    ) -> ProfessionalTrialBalanceResponse:
        """Return opening, movement and closing balances from POSTED entries only."""
        self._validate_range(start_date, end_date)
        opening_end = start_date - timedelta(days=1)
        opening_rows = await self.repository.account_movements(
            organization_id, end_date=opening_end
        )
        movement_rows = await self.repository.account_movements(
            organization_id, start_date, end_date
        )
        opening = {
            account.id: (account, debit, credit)
            for account, debit, credit in opening_rows
        }
        movement = {
            account.id: (account, debit, credit)
            for account, debit, credit in movement_rows
        }
        lines: list[ProfessionalTrialBalanceLine] = []
        totals = [Decimal("0.00") for _ in range(6)]
        for account_id in sorted(
            set(opening) | set(movement),
            key=lambda item: (opening.get(item) or movement[item])[0].code,
        ):
            account = (opening.get(account_id) or movement[account_id])[0]
            opening_debit_raw = opening.get(
                account_id, (account, Decimal("0.00"), Decimal("0.00"))
            )[1]
            opening_credit_raw = opening.get(
                account_id, (account, Decimal("0.00"), Decimal("0.00"))
            )[2]
            movement_debit = movement.get(
                account_id, (account, Decimal("0.00"), Decimal("0.00"))
            )[1]
            movement_credit = movement.get(
                account_id, (account, Decimal("0.00"), Decimal("0.00"))
            )[2]
            opening_debit, opening_credit = self._normal_balance_sides(
                account.account_type, opening_debit_raw, opening_credit_raw
            )
            closing_debit, closing_credit = self._normal_balance_sides(
                account.account_type,
                opening_debit_raw + movement_debit,
                opening_credit_raw + movement_credit,
            )
            values = (
                opening_debit,
                opening_credit,
                movement_debit,
                movement_credit,
                closing_debit,
                closing_credit,
            )
            totals = [
                total + value for total, value in zip(totals, values, strict=True)
            ]
            lines.append(
                ProfessionalTrialBalanceLine(
                    account_id=account.id,
                    code=account.code,
                    name=account.name,
                    account_type=account.account_type,
                    opening_debit=opening_debit,
                    opening_credit=opening_credit,
                    movement_debit=movement_debit,
                    movement_credit=movement_credit,
                    closing_debit=closing_debit,
                    closing_credit=closing_credit,
                )
            )
        return ProfessionalTrialBalanceResponse(
            start_date=start_date,
            end_date=end_date,
            lines=lines,
            total_opening_debit=totals[0],
            total_opening_credit=totals[1],
            total_movement_debit=totals[2],
            total_movement_credit=totals[3],
            total_closing_debit=totals[4],
            total_closing_credit=totals[5],
            is_opening_balanced=totals[0] == totals[1],
            is_movement_balanced=totals[2] == totals[3],
            is_closing_balanced=totals[4] == totals[5],
        )

    async def professional_financial_statement(
        self,
        organization_id: str,
        statement_code: str,
        end_date: date,
        start_date: date | None = None,
        framework: str = "SYSCOHADA",
    ) -> ProfessionalFinancialStatementResponse:
        if statement_code not in {"BALANCE_SHEET", "INCOME_STATEMENT"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unsupported professional financial statement",
            )
        if statement_code == "INCOME_STATEMENT" and start_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Income statement requires a start date",
            )
        if start_date is not None:
            self._validate_range(start_date, end_date)
        movements = await self.repository.account_movements(
            organization_id,
            start_date if statement_code == "INCOME_STATEMENT" else None,
            end_date,
        )
        mappings = await self.mappings.list_active(
            organization_id, framework, statement_code
        )
        mapping_by_account = {mapping.account_id: mapping for mapping in mappings}
        grouped: dict[tuple[str, str, str, str, str, int], Decimal] = {}
        unmapped_account_codes: list[str] = []
        relevant_types = (
            FinancialReportingRules.BALANCE_SHEET_TYPES
            | FinancialReportingRules.INCOME_STATEMENT_TYPES
            if statement_code == "BALANCE_SHEET"
            else FinancialReportingRules.INCOME_STATEMENT_TYPES
        )
        for account, debit, credit in movements:
            if account.account_type not in relevant_types:
                continue
            mapping = mapping_by_account.get(account.id)
            if mapping is None:
                unmapped_account_codes.append(account.code)
                continue
            balance = FinancialReportingRules.balance_for_account(
                account.account_type, debit, credit
            )
            if statement_code == "BALANCE_SHEET" and account.account_type == "EXPENSE":
                balance = -balance
            key = (
                mapping.presentation_role,
                mapping.section_code,
                mapping.section_label,
                mapping.line_code,
                mapping.line_label,
                mapping.display_order,
            )
            grouped[key] = grouped.get(key, Decimal("0.00")) + balance
        lines = [
            ProfessionalFinancialStatementLine(
                presentation_role=key[0],
                section_code=key[1],
                section_label=key[2],
                line_code=key[3],
                line_label=key[4],
                display_order=key[5],
                balance=balance,
            )
            for key, balance in sorted(
                grouped.items(), key=lambda item: (item[0][5], item[0][1], item[0][3])
            )
        ]
        total_assets = sum(
            (line.balance for line in lines if line.presentation_role == "ASSETS"),
            Decimal("0.00"),
        )
        total_liabilities_and_equity = sum(
            (
                line.balance
                for line in lines
                if line.presentation_role == "LIABILITIES_EQUITY"
            ),
            Decimal("0.00"),
        )
        total_revenue = sum(
            (line.balance for line in lines if line.presentation_role == "REVENUE"),
            Decimal("0.00"),
        )
        total_expense = sum(
            (line.balance for line in lines if line.presentation_role == "EXPENSE"),
            Decimal("0.00"),
        )
        is_balance_sheet = statement_code == "BALANCE_SHEET"
        net_result = None if is_balance_sheet else total_revenue - total_expense
        return ProfessionalFinancialStatementResponse(
            framework=framework,
            statement_code=statement_code,
            start_date=start_date,
            end_date=end_date,
            lines=lines,
            total=total_assets if is_balance_sheet else net_result or Decimal("0.00"),
            total_assets=total_assets if is_balance_sheet else None,
            total_liabilities_and_equity=(
                total_liabilities_and_equity if is_balance_sheet else None
            ),
            net_result=net_result,
            is_balanced=(
                total_assets == total_liabilities_and_equity
                if is_balance_sheet
                else None
            ),
            unmapped_account_codes=sorted(set(unmapped_account_codes)),
        )

    async def reconcile_reporting(
        self, organization_id: str, start_date: date, end_date: date
    ) -> ReportingReconciliationResponse:
        self._validate_range(start_date, end_date)
        trial = await self.professional_trial_balance(
            organization_id, start_date, end_date
        )
        balance_sheet = await self.balance_sheet(organization_id, end_date)
        professional_balance_sheet = await self.professional_financial_statement(
            organization_id, "BALANCE_SHEET", end_date
        )
        professional_balance_sheet_is_balanced = bool(
            professional_balance_sheet.is_balanced
        )
        professional_balance_sheet_is_complete = not (
            professional_balance_sheet.unmapped_account_codes
        )
        is_consistent = (
            trial.is_opening_balanced
            and trial.is_movement_balanced
            and trial.is_closing_balanced
            and balance_sheet.is_balanced
            and professional_balance_sheet_is_balanced
            and professional_balance_sheet_is_complete
        )
        return ReportingReconciliationResponse(
            start_date=start_date,
            end_date=end_date,
            trial_balance_is_balanced=(
                trial.is_opening_balanced
                and trial.is_movement_balanced
                and trial.is_closing_balanced
            ),
            balance_sheet_is_balanced=balance_sheet.is_balanced,
            professional_balance_sheet_is_balanced=professional_balance_sheet_is_balanced,
            professional_balance_sheet_is_complete=professional_balance_sheet_is_complete,
            unmapped_balance_sheet_account_codes=(
                professional_balance_sheet.unmapped_account_codes
            ),
            movement_debit=trial.total_movement_debit,
            movement_credit=trial.total_movement_credit,
            closing_debit=trial.total_closing_debit,
            closing_credit=trial.total_closing_credit,
            is_consistent=is_consistent,
        )

    async def export_professional_trial_balance_csv(
        self,
        organization_id: str,
        actor_user_id: str,
        start_date: date,
        end_date: date,
    ) -> str:
        report = await self.professional_trial_balance(
            organization_id, start_date, end_date
        )
        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "account_code",
                "account_name",
                "account_type",
                "opening_debit",
                "opening_credit",
                "movement_debit",
                "movement_credit",
                "closing_debit",
                "closing_credit",
            ]
        )
        for line in report.lines:
            writer.writerow(
                [
                    line.code,
                    line.name,
                    line.account_type,
                    str(line.opening_debit),
                    str(line.opening_credit),
                    str(line.movement_debit),
                    str(line.movement_credit),
                    str(line.closing_debit),
                    str(line.closing_credit),
                ]
            )
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PROFESSIONAL_TRIAL_BALANCE_EXPORTED",
            resource_type="ProfessionalTrialBalance",
            resource_id=f"{start_date.isoformat()}:{end_date.isoformat()}",
            context={"format": "csv", "line_count": len(report.lines)},
        )
        await self.session.commit()
        return output.getvalue()

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
    def _normal_balance_sides(
        account_type: str, debit: Decimal, credit: Decimal
    ) -> tuple[Decimal, Decimal]:
        balance = FinancialReportingRules.balance_for_account(
            account_type, debit, credit
        )
        debit_nature = account_type in {"ASSET", "EXPENSE"}
        if balance >= 0:
            return (
                (balance, Decimal("0.00"))
                if debit_nature
                else (Decimal("0.00"), balance)
            )
        return (
            (Decimal("0.00"), -balance) if debit_nature else (-balance, Decimal("0.00"))
        )

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )
