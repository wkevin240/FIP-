from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    CalculationStatus,
    SourceReference,
)
from app.domain.calculation.engine import CalculationEngine, CalculationNode


BALANCE_SHEET_CATEGORIES = ("ASSET", "LIABILITY", "EQUITY")
BALANCE_SHEET_TOTALS = (
    "TOTAL_ASSETS",
    "TOTAL_LIABILITIES",
    "TOTAL_EQUITY",
    "BALANCE_DIFFERENCE",
)


@dataclass(frozen=True, slots=True)
class BalanceSheetFact:
    """One immutable posted-ledger movement supplied by the accounting adapter."""

    posting_id: str
    account_id: str
    debit: Decimal
    credit: Decimal

    def __post_init__(self) -> None:
        if not self.posting_id.strip():
            raise ValueError("posting_id is required")
        if not self.account_id.strip():
            raise ValueError("account_id is required")
        if not isinstance(self.debit, Decimal) or not isinstance(self.credit, Decimal):
            raise TypeError("ledger amounts must use Decimal")


@dataclass(frozen=True, slots=True)
class BalanceSheetAccountRule:
    """Explicit balance-sheet classification; account codes are never inferred."""

    account_id: str
    category: str

    def __post_init__(self) -> None:
        if not self.account_id.strip():
            raise ValueError("account_id is required")
        if self.category not in BALANCE_SHEET_CATEGORIES:
            raise ValueError(f"unsupported balance-sheet category: {self.category}")


class LedgerBalanceSheetInputResolver:
    """Resolve authorized posted-ledger facts into deterministic balance-sheet inputs."""

    @staticmethod
    def _definition(code: str, rule_version: str) -> CalculationDefinition:
        return CalculationDefinition(
            code=code,
            formula="posted ledger fact",
            rule_version=rule_version,
        )

    @staticmethod
    def resolve(
        context: CalculationContext,
        facts: Iterable[BalanceSheetFact],
        rules: Iterable[BalanceSheetAccountRule],
    ) -> Mapping[str, CalculationResult]:
        rules_by_account: dict[str, BalanceSheetAccountRule] = {}
        for rule in rules:
            if rule.account_id in rules_by_account:
                raise ValueError(f"duplicate balance-sheet rule for account: {rule.account_id}")
            rules_by_account[rule.account_id] = rule

        amounts = {category: Decimal("0.00") for category in BALANCE_SHEET_CATEGORIES}
        sources: dict[str, list[SourceReference]] = {
            category: [] for category in BALANCE_SHEET_CATEGORIES
        }

        for fact in facts:
            if fact.debit < 0 or fact.credit < 0:
                raise ValueError(f"ledger fact {fact.posting_id} contains a negative amount")
            if (fact.debit > 0) == (fact.credit > 0):
                raise ValueError(
                    f"ledger fact {fact.posting_id} must have exactly one positive side"
                )

            rule = rules_by_account.get(fact.account_id)
            if rule is None:
                continue

            if rule.category == "ASSET":
                amount = fact.debit - fact.credit
            else:
                amount = fact.credit - fact.debit
            amounts[rule.category] += amount
            sources[rule.category].append(
                SourceReference(
                    record_type="LedgerPosting",
                    record_id=fact.posting_id,
                    module="accounting",
                )
            )

        results: dict[str, CalculationResult] = {}
        for category in BALANCE_SHEET_CATEGORIES:
            definition = LedgerBalanceSheetInputResolver._definition(category, context.rule_version)
            if not sources[category]:
                results[category] = CalculationResult.not_ready(
                    definition=definition,
                    context=context,
                    reason=f"no posted ledger movement is mapped to {category}",
                )
            else:
                results[category] = CalculationResult.ready(
                    definition=definition,
                    context=context,
                    value=amounts[category],
                    sources=tuple(sources[category]),
                )
        return results


class BalanceSheetCalculationEngine:
    """Execute the balance-sheet equation through the shared FIP calculation DAG."""

    @staticmethod
    def calculate(
        context: CalculationContext,
        inputs: Mapping[str, CalculationResult],
    ) -> dict[str, CalculationResult]:
        missing = set(BALANCE_SHEET_CATEGORIES) - inputs.keys()
        if missing:
            raise ValueError(f"missing balance-sheet inputs: {', '.join(sorted(missing))}")

        definitions = {
            "TOTAL_ASSETS": CalculationDefinition(
                code="TOTAL_ASSETS",
                formula="ASSET",
                dependencies=("ASSET",),
                rule_version=context.rule_version,
            ),
            "TOTAL_LIABILITIES": CalculationDefinition(
                code="TOTAL_LIABILITIES",
                formula="LIABILITY",
                dependencies=("LIABILITY",),
                rule_version=context.rule_version,
            ),
            "TOTAL_EQUITY": CalculationDefinition(
                code="TOTAL_EQUITY",
                formula="EQUITY",
                dependencies=("EQUITY",),
                rule_version=context.rule_version,
            ),
            "BALANCE_DIFFERENCE": CalculationDefinition(
                code="BALANCE_DIFFERENCE",
                formula="TOTAL_ASSETS - TOTAL_LIABILITIES - TOTAL_EQUITY",
                dependencies=("TOTAL_ASSETS", "TOTAL_LIABILITIES", "TOTAL_EQUITY"),
                rule_version=context.rule_version,
            ),
        }
        graph = CalculationEngine(
            nodes=(
                CalculationNode(definitions["TOTAL_ASSETS"], lambda values: values[0]),
                CalculationNode(definitions["TOTAL_LIABILITIES"], lambda values: values[0]),
                CalculationNode(definitions["TOTAL_EQUITY"], lambda values: values[0]),
                CalculationNode(
                    definitions["BALANCE_DIFFERENCE"],
                    lambda values: values[0] - values[1] - values[2],
                ),
            ),
            external_input_codes=BALANCE_SHEET_CATEGORIES,
        )
        return {
            code: result
            for code, result in graph.execute(context, inputs).items()
            if code in BALANCE_SHEET_TOTALS
        }
