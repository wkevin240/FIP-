from collections.abc import Mapping
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    CalculationStatus,
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

        definitions = cls._DEFINITIONS
        nodes = (
            CalculationNode(
                definitions["GROSS_PROFIT"],
                lambda values: values[0] - values[1],
            ),
            CalculationNode(
                definitions["OPERATING_INCOME"],
                lambda values: values[0] - values[1],
            ),
            CalculationNode(
                definitions["NET_INCOME"],
                lambda values: values[0] + values[1] - values[2],
            ),
        )
        results = CalculationEngine(
            nodes, external_input_codes=CATEGORY_CODES
        ).execute(context, inputs)
        revenue = inputs["REVENUE"]
        derived = {
            code: results[code]
            for code in ("GROSS_PROFIT", "OPERATING_INCOME", "NET_INCOME")
        }
        for code, numerator_code in (
            ("GROSS_MARGIN", "GROSS_PROFIT"),
            ("OPERATING_MARGIN", "OPERATING_INCOME"),
            ("NET_MARGIN", "NET_INCOME"),
        ):
            definition = CalculationDefinition(
                code=code,
                formula=f"{numerator_code} / REVENUE",
                dependencies=(numerator_code, "REVENUE"),
            )
            numerator = derived[numerator_code]
            sources = tuple(dict.fromkeys((*numerator.sources, *revenue.sources)))
            if numerator.status != CalculationStatus.READY:
                results[code] = CalculationResult(
                    definition=definition,
                    context=context,
                    status=numerator.status,
                    reason=f"Dependency {numerator.definition.code}: {numerator.reason}",
                    sources=sources,
                )
            elif revenue.status != CalculationStatus.READY:
                results[code] = CalculationResult(
                    definition=definition,
                    context=context,
                    status=revenue.status,
                    reason=f"Dependency {revenue.definition.code}: {revenue.reason}",
                    sources=sources,
                )
            elif revenue.value == Decimal("0"):
                results[code] = CalculationResult.not_ready(
                    definition,
                    context,
                    "Revenue is zero; ratio denominator is zero",
                    sources=sources,
                )
            else:
                value = (numerator.value / revenue.value).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                results[code] = CalculationResult.ready(
                    definition,
                    context,
                    value,
                    sources=sources,
                )
        return results

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
