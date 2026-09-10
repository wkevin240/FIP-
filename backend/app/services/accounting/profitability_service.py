from collections.abc import Iterable

from app.domain.calculation.accounting_profitability import ProfitabilityCalculationEngine
from app.domain.calculation.contracts import CalculationContext, CalculationResult
from app.domain.calculation.ledger_profitability import (
    LedgerProfitabilityInputResolver,
    ProfitabilityAccountRule,
)
from app.services.accounting.ledger_service import LedgerService


class LedgerProfitabilityIntegrityError(RuntimeError):
    """Raised when the selected ledger slice cannot be trusted for P&L calculation."""


class LedgerProfitabilityService:
    """Compose the authoritative ledger adapter with the deterministic P&L kernel.

    The service owns orchestration only. LedgerService remains responsible for
    tenant-scoped persistence reads and reconciliation; account classification
    remains explicit configuration; ProfitabilityCalculationEngine remains
    responsible for deterministic formulas and status propagation.
    """

    def __init__(self, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service

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
