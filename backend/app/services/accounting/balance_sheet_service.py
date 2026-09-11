from collections.abc import Iterable

from app.domain.calculation.accounting_balance_sheet import (
    BalanceSheetAccountRule,
    BalanceSheetCalculationEngine,
    LedgerBalanceSheetInputResolver,
)
from app.domain.calculation.contracts import CalculationContext, CalculationResult
from app.models.accounting.balance_sheet_mapping import BalanceSheetAccountMapping
from app.repositories.accounting.balance_sheet_mapping_repository import BalanceSheetMappingRepository
from app.services.accounting.ledger_service import LedgerService


class BalanceSheetMappingAmbiguityError(RuntimeError):
    """Raised when multiple effective mappings cover one account at a snapshot date."""

    def __init__(self, account_ids: Iterable[str]) -> None:
        self.account_ids = tuple(sorted(set(account_ids)))
        super().__init__(
            "balance-sheet mapping is ambiguous at snapshot date; "
            f"multiple effective mappings exist for account(s): {', '.join(self.account_ids)}"
        )


class LedgerBalanceSheetService:
    """Build a read-only closing balance sheet from cumulative posted-ledger facts."""

    def __init__(
        self,
        ledger_service: LedgerService,
        mapping_repository: BalanceSheetMappingRepository,
    ) -> None:
        self.ledger_service = ledger_service
        self.mapping_repository = mapping_repository

    @staticmethod
    def _rules(mappings: Iterable[BalanceSheetAccountMapping]) -> tuple[BalanceSheetAccountRule, ...]:
        return tuple(
            BalanceSheetAccountRule(account_id=m.account_id, category=m.category)
            for m in mappings
        )

    @staticmethod
    def _ensure_unambiguous(
        mappings: Iterable[BalanceSheetAccountMapping],
    ) -> tuple[BalanceSheetAccountMapping, ...]:
        materialized = tuple(mappings)
        by_account: dict[str, list[BalanceSheetAccountMapping]] = {}
        for mapping in materialized:
            by_account.setdefault(mapping.account_id, []).append(mapping)
        ambiguous = [account_id for account_id, items in by_account.items() if len(items) > 1]
        if ambiguous:
            raise BalanceSheetMappingAmbiguityError(ambiguous)
        return materialized

    async def calculate(
        self,
        context: CalculationContext,
        rules: Iterable[BalanceSheetAccountRule],
        *,
        fiscal_period_id: str | None = None,
    ) -> dict[str, CalculationResult]:
        facts = await self.ledger_service.balance_sheet_facts(
            context.organization_id,
            fiscal_period_id=fiscal_period_id,
            end_date=context.period_end,
        )
        inputs = LedgerBalanceSheetInputResolver.resolve(context, facts, rules)
        return BalanceSheetCalculationEngine.calculate(context, inputs)

    async def calculate_from_persisted_mappings(
        self,
        context: CalculationContext,
        *,
        fiscal_period_id: str | None = None,
    ) -> dict[str, CalculationResult]:
        mappings = await self.mapping_repository.list_effective_at(
            context.organization_id,
            context.rule_version,
            context.period_end,
        )
        mappings = self._ensure_unambiguous(mappings)
        return await self.calculate(
            context,
            self._rules(mappings),
            fiscal_period_id=fiscal_period_id,
        )
