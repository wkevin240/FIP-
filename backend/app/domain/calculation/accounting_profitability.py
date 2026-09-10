from collections.abc import Mapping
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    SourceReference,
)
from app.domain.calculation.engine import CalculationEngine, CalculationNode

CENT = Decimal("0.01")

CATEGORY_CODES = (
    "REVENUE",
    "COGS",
    "OPERATING_EXPENSE",
    "OTHER_INCOME",
    "OTHER_EXPENSE",
)


class ProfitabilityCalculationEngine:
    """Accounting profitability DAG over already-resolved ledger facts.

    The engine owns profitability formulas only. Data access, tenant filtering,
    ledger posting and account-to-category mapping remain outside the domain
    calculation layer.
    """

    _DEFINITIONS = {
        "GROSS_PROFIT": CalculationDefinition(
            code="GROSS_PROFIT",
            formula="REVENUE - COGS",
            dependencies=("REVENUE", "COGS"),
        ),
        "OPERATING_INCOME": CalculationDefinition(
            code="OPERATING_INCOME",
            formula="GROSS_PROFIT - OPERATING_EXPENSE",
            dependencies=("GROSS_PROFIT", "OPERATING_EXPENSE"),
        ),
        "NET_INCOME": CalculationDefinition(
            code="NET_INCOME",
            formula="OPERATING_INCOME + OTHER_INCOME - OTHER_EXPENSE",
            dependencies=("OPERATING_INCOME", "OTHER_INCOME", "OTHER_EXPENSE"),
        ),
        "GROSS_MARGIN": CalculationDefinition(
            code="GROSS_MARGIN",
            formula="GROSS_PROFIT / REVENUE",
            dependencies=("GROSS_PROFIT", "REVENUE"),
        ),
        "OPERATING_MARGIN": CalculationDefinition(
            code="OPERATING_MARGIN",
            formula="OPERATING_INCOME / REVENUE",
            dependencies=("OPERATING_INCOME", "REVENUE"),
        ),
        "NET_MARGIN": CalculationDefinition(
            code="NET_MARGIN",
            formula="NET_INCOME / REVENUE",
            dependencies=("NET_INCOME", "REVENUE"),
        ),
    }

    @classmethod
    def calculate(
        cls,
        context: CalculationContext,
        inputs: Mapping[str, CalculationResult],
    ) -> dict[str, CalculationResult]:
        missing = set(CATEGORY_CODES) - inputs.keys()
        if missing:
            raise ValueError(
                "profitability inputs missing required categories: "
                + ", ".join(sorted(missing))
            )

        def money_subtract(values: tuple[Decimal, ...]) -> Decimal:
            return (values[0] - values[1]).quantize(CENT, rounding=ROUND_HALF_UP)

        def money_income(values: tuple[Decimal, ...]) -> Decimal:
            return (values[0] + values[1] - values[2]).quantize(CENT, rounding=ROUND_HALF_UP)

        def ratio(values: tuple[Decimal, ...]) -> Decimal:
            return (values[0] / values[1]).quantize(CENT, rounding=ROUND_HALF_UP)

        nodes = (
            CalculationNode(cls._DEFINITIONS["GROSS_PROFIT"], money_subtract),
            CalculationNode(cls._DEFINITIONS["OPERATING_INCOME"], money_subtract),
            CalculationNode(cls._DEFINITIONS["NET_INCOME"], money_income),
            CalculationNode(cls._DEFINITIONS["GROSS_MARGIN"], ratio),
            CalculationNode(cls._DEFINITIONS["OPERATING_MARGIN"], ratio),
            CalculationNode(cls._DEFINITIONS["NET_MARGIN"], ratio),
        )
        return CalculationEngine(
            nodes, external_input_codes=CATEGORY_CODES
        ).execute(context, inputs)

    @staticmethod
    def source_result(
        context: CalculationContext,
        code: str,
        value: Decimal | None,
        *,
        reason: str | None = None,
        sources: tuple[SourceReference, ...] = (),
        formula: str = "posted ledger fact",
    ) -> CalculationResult:
        definition = CalculationDefinition(code=code, formula=formula)
        if value is not None:
            return CalculationResult.ready(
                definition, context, value, sources=sources
            )
        return CalculationResult.not_ready(
            definition,
            context,
            reason or f"{code} is not available from the resolved ledger facts",
            sources=sources,
        )


def profitability_context(
    organization_id: str,
    period_start: date,
    period_end: date,
    *,
    currency: str | None = None,
    dimension_id: str | None = None,
    dimension_value_id: str | None = None,
    rule_version: str = "1",
) -> CalculationContext:
    return CalculationContext(
        organization_id=organization_id,
        period_start=period_start,
        period_end=period_end,
        currency=currency,
        dimension_id=dimension_id,
        dimension_value_id=dimension_value_id,
        rule_version=rule_version,
    )
