from datetime import date, timedelta
from decimal import Decimal

from app.repositories.accounting.cash_flow_account_mapping_repository import (
    CashFlowAccountMappingRepository,
)
from app.repositories.accounting.cash_flow_repository import CashFlowRepository
from app.schemas.accounting.cash_flow import (
    CashFlowStatementLine,
    CashFlowStatementResponse,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class CashFlowService:
    def __init__(self, session: AsyncSession) -> None:
        self.mappings = CashFlowAccountMappingRepository(session)
        self.repository = CashFlowRepository(session)

    async def statement(
        self, organization_id: str, start_date: date, end_date: date
    ) -> CashFlowStatementResponse:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )
        mappings = await self.mappings.list_active(organization_id)
        cash_account_ids = {
            mapping.account_id for mapping in mappings if mapping.is_cash_account
        }
        if not cash_account_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="At least one active cash-flow cash account must be configured",
            )
        category_by_account = {
            mapping.account_id: mapping.cash_flow_category
            for mapping in mappings
            if not mapping.is_cash_account
        }
        amounts = {
            "OPERATING": Decimal("0.00"),
            "INVESTING": Decimal("0.00"),
            "FINANCING": Decimal("0.00"),
            "UNCLASSIFIED": Decimal("0.00"),
        }
        counts = {category: 0 for category in amounts}
        unclassified_entry_numbers: list[str] = []
        opening_cash = await self.repository.cash_balance(
            organization_id, cash_account_ids, start_date - timedelta(days=1)
        )
        for entry in await self.repository.recognized_entries_with_cash_activity(
            organization_id, cash_account_ids, start_date, end_date
        ):
            cash_delta = sum(
                (
                    Decimal(line.debit) - Decimal(line.credit)
                    for line in entry.lines
                    if line.account_id in cash_account_ids
                ),
                Decimal("0.00"),
            )
            if cash_delta == Decimal("0.00"):
                continue
            counterpart_account_ids = {
                line.account_id
                for line in entry.lines
                if line.account_id not in cash_account_ids
            }
            counterpart_categories = {
                category_by_account.get(account_id)
                for account_id in counterpart_account_ids
            }
            if None in counterpart_categories or len(counterpart_categories) != 1:
                category = "UNCLASSIFIED"
                unclassified_entry_numbers.append(entry.entry_number)
            else:
                category = counterpart_categories.pop()
            amounts[category] += cash_delta
            counts[category] += 1
        closing_cash = await self.repository.cash_balance(
            organization_id, cash_account_ids, end_date
        )
        net_cash_flow = (
            amounts["OPERATING"]
            + amounts["INVESTING"]
            + amounts["FINANCING"]
            + amounts["UNCLASSIFIED"]
        )
        computed_closing_cash = opening_cash + net_cash_flow
        lines = [
            CashFlowStatementLine(
                category=category,
                amount=amounts[category],
                entry_count=counts[category],
            )
            for category in ("OPERATING", "INVESTING", "FINANCING", "UNCLASSIFIED")
        ]
        return CashFlowStatementResponse(
            start_date=start_date,
            end_date=end_date,
            opening_cash=opening_cash,
            operating_cash_flow=amounts["OPERATING"],
            investing_cash_flow=amounts["INVESTING"],
            financing_cash_flow=amounts["FINANCING"],
            unclassified_cash_flow=amounts["UNCLASSIFIED"],
            net_cash_flow=net_cash_flow,
            closing_cash=closing_cash,
            computed_closing_cash=computed_closing_cash,
            is_reconciled=closing_cash == computed_closing_cash,
            is_complete=not unclassified_entry_numbers,
            unclassified_entry_numbers=sorted(unclassified_entry_numbers),
            lines=lines,
        )
