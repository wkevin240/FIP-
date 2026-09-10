from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.domain.calculation.accounting_profitability import CATEGORY_CODES
from app.domain.calculation.contracts import CalculationContext, CalculationResult, SourceReference


@dataclass(frozen=True, slots=True)
class LedgerProfitabilityFact:
    """One immutable posted-ledger movement supplied by the accounting adapter."""

    posting_id: str
    account_id: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True, slots=True)
class ProfitabilityAccountRule:
    """Explicit account classification used to resolve ledger facts into P&L inputs."""

    account_id: str
    category: str


class LedgerProfitabilityInputResolver:
    """Resolve posted ledger movements into the kernel's profitability source inputs.

    This adapter deliberately accepts already-authorized ledger facts. It does not
    query the database, infer account classes from account codes, or manufacture
    zero-valued categories. Classification is supplied explicitly by configuration.
    """

    @staticmethod
    def resolve(
        context: CalculationContext,
        facts: Iterable[LedgerProfitabilityFact],
        rules: Iterable[ProfitabilityAccountRule],
    ) -> Mapping[str, CalculationResult]:
        rules_by_account: dict[str, ProfitabilityAccountRule] = {}
        for rule in rules:
            if rule.category not in CATEGORY_CODES:
                raise ValueError(f"unsupported profitability category: {rule.category}")
            if rule.account_id in rules_by_account:
                raise ValueError(f"duplicate profitability rule for account: {rule.account_id}")
            rules_by_account[rule.account_id] = rule

        amounts = {category: Decimal("0.00") for category in CATEGORY_CODES}
        sources: dict[str, list[SourceReference]] = {category: [] for category in CATEGORY_CODES}
        matched_accounts: set[str] = set()

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

            matched_accounts.add(fact.account_id)
            if rule.category in {"REVENUE", "OTHER_INCOME"}:
                amount = fact.credit - fact.debit
            else:
                amount = fact.debit - fact.credit
            amounts[rule.category] += amount
            sources[rule.category].append(
                SourceReference(
                    record_type="LedgerPosting",
                    record_id=fact.posting_id,
                    module="accounting",
                )
            )

        results: dict[str, CalculationResult] = {}
        for category in CATEGORY_CODES:
            if not sources[category]:
                results[category] = CalculationResult.not_ready(
                    definition=CalculationResult.source_result_definition(category),
                    context=context,
                    reason=f"no posted ledger movement is mapped to {category}",
                )
                continue
            results[category] = CalculationResult.ready(
                definition=CalculationResult.source_result_definition(category),
                context=context,
                value=amounts[category],
                sources=tuple(sources[category]),
                metadata={"account_ids": sorted(
                    account_id
                    for account_id in matched_accounts
                    if rules_by_account[account_id].category == category
                )},
            )

        return results
