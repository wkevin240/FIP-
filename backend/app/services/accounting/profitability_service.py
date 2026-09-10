from collections.abc import Iterable

from app.domain.calculation.accounting_profitability import ProfitabilityCalculationEngine
from app.domain.calculation.contracts import CalculationContext, CalculationResult
from app.domain.calculation.ledger_profitability import (
    LedgerProfitabilityInputResolver,
    ProfitabilityAccountRule,
)
from app.services.accounting.ledger_service import LedgerService


class LedgerProfitabilityService:
    """Compose the authoritative ledger adapter with the deterministic P&L kernel.

    The service owns orchestration only. LedgerService remains responsible for
    tenant-scoped persistence reads; account classification remains explicit
    configuration; ProfitabilityCalculationEngine remains responsible for
    deterministic formulas and status propagation.
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
        """Calculate profitability from the selected posted-ledger slice.

        The calculation window is taken directly from the immutable execution
        context. No account mapping is inferred and no missing category is
        converted to zero by this orchestration layer.
        """
        facts = await self.ledger_service.profitability_facts(
            context.organization_id,
            fiscal_period_id=fiscal_period_id,
            start_date=context.period_start,
            end_date=context.period_end,
        )
        inputs = LedgerProfitabilityInputResolver.resolve(context, facts, rules)
        return ProfitabilityCalculationEngine.calculate(context, inputs)
