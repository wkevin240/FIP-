from collections.abc import Iterable

from app.domain.calculation.accounting_profitability import ProfitabilityCalculationEngine
from app.domain.calculation.contracts import CalculationContext, CalculationResult
from app.domain.calculation.ledger_profitability import (
    LedgerProfitabilityInputResolver,
    ProfitabilityAccountRule,
)
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping
from app.repositories.accounting.profitability_mapping_repository import ProfitabilityMappingRepository
from app.services.accounting.ledger_service import LedgerService


class LedgerProfitabilityIntegrityError(RuntimeError):
    """Raised when the selected ledger slice cannot be trusted for P&L calculation."""


class ProfitabilityMappingAmbiguityError(RuntimeError):
    """Raised when more than one effective mapping intersects the calculation window."""

    def __init__(self, account_ids: Iterable[str]) -> None:
        self.account_ids = tuple(sorted(set(account_ids)))
        super().__init__(
            "profitability mapping is ambiguous for calculation period; "
            f"multiple effective mappings intersect account(s): {', '.join(self.account_ids)}"
        )


class LedgerProfitabilityService:
    """Compose the authoritative ledger adapter with the deterministic P&L kernel.

    The service owns orchestration only. LedgerService remains responsible for
    tenant-scoped persistence reads and reconciliation; account classification
    remains explicit configuration; ProfitabilityCalculationEngine remains
    responsible for deterministic formulas and status propagation.
    """

    def __init__(
        self,
        ledger_service: LedgerService,
        mapping_repository: ProfitabilityMappingRepository | None = None,
    ) -> None:
        self.ledger_service = ledger_service
        self.mapping_repository = mapping_repository

    @staticmethod
    def _rules_from_mappings(
        mappings: Iterable[ProfitabilityAccountMapping],
    ) -> tuple[ProfitabilityAccountRule, ...]:
        return tuple(
            ProfitabilityAccountRule(
                account_id=mapping.account_id,
                category=mapping.category,
            )
            for mapping in mappings
        )

    @staticmethod
    def _ensure_unambiguous_mappings(
        mappings: Iterable[ProfitabilityAccountMapping],
    ) -> tuple[ProfitabilityAccountMapping, ...]:
        materialized = tuple(mappings)
        by_account: dict[str, list[ProfitabilityAccountMapping]] = {}
        for mapping in materialized:
            by_account.setdefault(mapping.account_id, []).append(mapping)

        ambiguous = [
            account_id
            for account_id, account_mappings in by_account.items()
            if len(account_mappings) > 1
        ]
        if ambiguous:
            raise ProfitabilityMappingAmbiguityError(ambiguous)
        return materialized

    async def calculate(
        self,
        context: CalculationContext,
        rules: Iterable[ProfitabilityAccountRule],
        *,
        fiscal_period_id: str | None = None,
    ) -> dict[str, CalculationResult]:
        """Calculate profitability from a reconciled posted-ledger slice.

        Reconciliation is a hard integrity gate: a P&L result must not be
        produced from a ledger slice that is known to differ from its POSTED
        journal source. No account mapping is inferred and no missing category
        is converted to zero by this orchestration layer.
        """
        reconciliation = await self.ledger_service.reconcile_postings(
            context.organization_id,
            fiscal_period_id=fiscal_period_id,
            start_date=context.period_start,
            end_date=context.period_end,
        )
        if not reconciliation["is_reconciled"]:
            raise LedgerProfitabilityIntegrityError(
                "cannot calculate profitability from an unreconciled ledger slice: "
                f"missing={reconciliation['missing_postings']}, "
                f"orphan={reconciliation['orphan_postings']}, "
                f"mismatched={reconciliation['mismatched_postings']}"
            )

        facts = await self.ledger_service.profitability_facts(
            context.organization_id,
            fiscal_period_id=fiscal_period_id,
            start_date=context.period_start,
            end_date=context.period_end,
        )
        inputs = LedgerProfitabilityInputResolver.resolve(context, facts, rules)
        return ProfitabilityCalculationEngine.calculate(context, inputs)

    async def calculate_from_persisted_mappings(
        self,
        context: CalculationContext,
        *,
        fiscal_period_id: str | None = None,
    ) -> dict[str, CalculationResult]:
        """Calculate using only mappings persisted for this tenant and rule version."""
        if self.mapping_repository is None:
            raise RuntimeError("profitability mapping repository is required for persisted mappings")
        mappings = await self.mapping_repository.list_for_period(
            context.organization_id,
            context.rule_version,
            context.period_start,
            context.period_end,
        )
        mappings = self._ensure_unambiguous_mappings(mappings)
        rules = self._rules_from_mappings(mappings)
        return await self.calculate(context, rules, fiscal_period_id=fiscal_period_id)
