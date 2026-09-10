# FIP Calculation Architecture

## Decision

FIP uses a **shared calculation kernel plus one calculation engine per business branch**. The kernel is intentionally small and proven through a real end-to-end calculation before additional infrastructure is introduced.

```text
Financial Calculation Kernel
      |
      +-- typed DAG execution
      +-- Decimal arithmetic boundary
      +-- status propagation
      +-- provenance
      +-- execution context
      |
      +-- Accounting Calculation Engine
      +-- Finance Calculation Engine
      +-- Banking Calculation Engine
      +-- Tax Calculation Engine
```

## Kernel-first, engine-first delivery strategy

The kernel must not become a multi-month platform project detached from business value. The first vertical slice is:

1. DAG dependency resolution.
2. Typed Decimal operators; never `eval()`.
3. `READY`, `NOT_READY`, `INCOMPLETE` and `ERROR` propagation.
4. A complete profitability/P&L calculation over authoritative posted data.
5. Source provenance and an execution trace sufficient to reproduce the result.
6. Tests against real repository schemas and PostgreSQL fixtures where integration coverage exists.

The profitability formula slice is intentionally small. It must be connected to the existing posted-ledger query path rather than maintaining a second data-access implementation. The existing profitability service is the candidate branch integration point; its synthetic test fixture is **not** accepted as proof of the kernel against a real grand livre.

Only capabilities proven necessary by that vertical slice should be promoted into the kernel.

## Execution context integrity

Every calculation execution has an immutable `CalculationContext` containing organization, period boundaries, rule version, and optional currency and analytical dimension. Before any DAG node executes, the kernel verifies that every supplied input result belongs to the same organization, period, analytical dimension, currency and rule-version context as the execution context. It also requires each input's calculation definition and every executable node definition to use the same rule version as the execution context.

This is a hard boundary, not an informational warning. A cross-organization, cross-period, cross-currency, cross-rule-version or cross-analytical-slice result is rejected instead of being combined with otherwise valid amounts. A calculation definition from another rule version is rejected as well. The kernel does not silently coerce or transform the mismatched input or execute a node under an unrelated rule version.

## Accounting reporting boundary

The accounting read side derives reporting exclusively from immutable `LedgerPosting` rows. The reporting endpoints support three explicit filters:

- `fiscal_period_id` for an organization-owned fiscal period;
- `start_date` as an inclusive posting-date lower bound;
- `end_date` as an inclusive posting-date upper bound.

A supplied fiscal-period identifier is tenant-validated before it is used. When a period is selected, explicit dates must remain within that period. Date ranges reject `start_date > end_date`. Without filters, the existing all-postings behavior is preserved for backward compatibility.

This layer does not reconstruct draft journal entries and does not silently include unposted state. Account balances and trial balance totals remain projections of the selected posted movements.

For an account movement report, the selected range determines the movements displayed. When `start_date` is supplied, `opening_balance` is calculated from all prior posted movements for the account in the organization, not merely from the selected fiscal period. When only a fiscal period is supplied, the opening balance is calculated from postings before that period's start date, allowing balances to carry forward across fiscal periods. The selected range movements are then applied to derive `closing_balance`. When neither a start date nor fiscal period is supplied, opening balance is zero because the report starts at the first available posting in its scope.

This distinction keeps a fiscal-period grand ledger faithful to the account's carried-forward balance while preserving the period/date filter for the displayed movements.

## Posting reconciliation control

The accounting read side also exposes a reconciliation control between POSTED journal lines and immutable ledger postings. For a selected organization and optional period/date scope, it reports missing postings, orphan postings and postings whose account, debit, credit or fiscal-period identity differs from the journal line. `is_reconciled` is true only when all discrepancy sets are empty. This is a detection control: it does not mutate either side or manufacture a correction.

Profitability orchestration treats this reconciliation state as a hard source-integrity gate. `LedgerProfitabilityService` refuses to calculate P&L from an unreconciled selected slice and raises `LedgerProfitabilityIntegrityError` with the detected discrepancy identifiers. This prevents a downstream financial result from appearing valid when the posted-ledger source is known to have drifted from its POSTED journal source.

## Profitability vertical slice

`ProfitabilityCalculationEngine` expresses Gross Profit, Operating Income, Net Income, Gross Margin, Operating Margin and Net Margin as a single kernel DAG. Category facts (`REVENUE`, `COGS`, `OPERATING_EXPENSE`, `OTHER_INCOME`, `OTHER_EXPENSE`) are explicit external inputs; all six derived metrics are calculation nodes. Monetary outputs are quantized to cents and ratios use the same deterministic Decimal operator boundary as the kernel.

`LedgerProfitabilityInputResolver` is the accounting-to-kernel boundary for this slice. It consumes only already-authorized posted-ledger movements plus an explicit account-to-category configuration. It applies the normal-debit/normal-credit sign convention needed to turn mapped ledger movements into positive P&L source facts, retains each contributing `LedgerPosting` as provenance, and returns `NOT_READY` when a category has no mapped posted movement. It never infers a category from an account code and never substitutes an unmapped category with zero.

The adapter's input contract is strict: posting and account identifiers must be present, debit and credit amounts must be `Decimal`, and each ledger movement must have exactly one positive side. Mapping rules must identify an account and a supported profitability category, and an account can have only one classification within a resolution. The resolver binds every emitted source definition to the `CalculationContext.rule_version`, preventing a source fact from being executed under a different rule version.

A zero revenue denominator is therefore an execution `ERROR` rather than a synthetic zero or a missing-data substitution. If an upstream profitability fact is `NOT_READY` or `ERROR`, the corresponding downstream metrics inherit that status through normal DAG propagation. This keeps the business engine aligned with the kernel's status contract instead of maintaining a parallel status implementation.

The database boundary is now explicit: `LedgerService.profitability_facts()` is the tenant- and period/date-scoped extraction point. It returns only immutable `LedgerProfitabilityFact` values and performs no account classification or profitability calculation. The domain resolver then consumes those facts together with explicitly supplied `ProfitabilityAccountRule` values. This keeps SQL access in the accounting service while keeping mapping and formulas deterministic and database-free.

`ProfitabilityAccountMapping` provides the persistence boundary for explicit account classification. A mapping is tenant-scoped, tied to a `rule_version`, and bounded by `effective_from`/`effective_to`; the database rejects an inverted effective range and, through a PostgreSQL exclusion constraint, rejects overlapping effective ranges for the same organization, account and rule version. The repository validates the same invariants before writes, verifies that the account belongs to the target organization, and exposes tenant-scoped create/update operations. `ProfitabilityMappingRepository.list_for_period()` retrieves only mappings belonging to the requested organization and rule version whose effective interval intersects the calculation period. If multiple effective mappings for the same account intersect a calculation period, the existing domain duplicate-classification guard rejects the ambiguity rather than choosing one silently. The database exclusion constraint is the race-safe backstop; application checks provide deterministic errors before normal writes reach the database.

`LedgerProfitabilityService` composes those boundaries for an executable application path: it first reconciles the selected POSTED journal/ledger slice, refuses to continue when reconciliation detects drift, derives the extraction window from the immutable `CalculationContext`, requests the tenant-scoped ledger facts from `LedgerService`, resolves them with explicit account rules, and passes the resulting source results to `ProfitabilityCalculationEngine`. `calculate_from_persisted_mappings()` additionally loads only mappings for the context organization and rule version before invoking that same path. It does not persist, mutate, infer mappings, or replace missing categories.

## Calculation status semantics

- `READY`: all dependencies are valid and the calculation produced a value.
- `NOT_READY`: a required business input is unavailable or not configured. This is a data/readiness condition, not a computational failure.
- `INCOMPLETE`: the calculation cannot be considered complete because required source coverage or reconciliation is incomplete.
- `ERROR`: the inputs were otherwise ready, but execution failed, for example division by zero or an invalid operator result.

For a calculated node, dependency status is monotonic and uses the worst dependency status with this priority:

`ERROR > NOT_READY > INCOMPLETE > READY`

Therefore an `ERROR` at a leaf must remain `ERROR` through every downstream node. Likewise, `NOT_READY` must not become zero or `READY` merely because another dependency is available.

A status must never be silently converted to zero. User-facing alerts and operational monitoring must distinguish missing data (`NOT_READY`) from a broken calculation (`ERROR`).

## Proof gates before extension

No new generic kernel module or business engine should be added until these three test categories are present and passing:

### 1. Non-regression

A frozen, authoritative posted grand-ledger snapshot with an independently verified expected result must be checked on every run. The first P&L proof must calculate Gross Profit, Operating Income and Net Income from that same posted ledger and compare the kernel output with an independent manual or Sage 100 calculation to the centime.

The current repository does not contain an authoritative real grand-ledger snapshot and the connected Supabase project is currently inactive. Therefore the P&L proof is a **blocked verification gate**, not a fabricated fixture. The existing generated PostgreSQL profitability fixture may test plumbing but must not be described as real-world proof.

Required evidence for closing this gate:

```text
same posted grand ledger
        |
        +--> FIP posted-ledger extraction --> explicit account mapping --> kernel DAG --> P&L result
        |
        +--> independent manual/Sage 100 calculation --> P&L result
        |
        +--> cent-level comparison --> PASS
```

### 2. Property

Accounting write-generation tests must generate many randomized balanced journal cases and assert the invariant `SUM(DEBITS) == SUM(CREDITS)` for every case. This is an invariant test, not a hand-written example test. Where the repository's journal-entry service is available to the test, the generated cases should pass through that service rather than bypassing it.

### 3. Status propagation

At minimum:

- remove a required source -> downstream result is `NOT_READY`, with `value is None`, without a crash and without substituting zero;
- force division by zero while inputs are `READY` -> downstream result is `ERROR`, with `value is None`, without a crash;
- force a leaf `ERROR` in a three-level DAG -> intermediate and final metrics remain `ERROR`.

## Branch responsibilities

### Accounting Calculation Engine

Consumes authoritative posted accounting state and owns accounting-derived calculations such as account balances, trial balance, statement totals, depreciation and provisions when their underlying domain contracts exist.

### Finance Calculation Engine

Consumes validated accounting, treasury and operational facts. Owns management and financial analysis such as margins, profitability, working capital, liquidity ratios, DSO/DPO and variance analysis.

### Banking Calculation Engine

Consumes normalized banking transactions and reconciliation state. Owns bank balance, reconciliation difference, cash position and banking exposure calculations.

### Tax Calculation Engine

Consumes validated taxable facts and versioned tax rules. Owns tax bases, liabilities, reconciliation and declaration calculations.

## Jurisdiction and rule model

Jurisdiction is **not a single interchangeable attribute across all engines**.

Accounting rules can reference a reporting framework such as `OHADA_SYSCOHADA`, `IFRS`, or a sector-specific framework, with an applicable scope and effective version. The official OHADA AUDCIF incorporates the revised SYSCOHADA and establishes the accounting rules, chart of accounts and financial reporting framework for the OHADA States.

Tax rules require a separate legal scope because taxation remains tied to national legislation and administration. Therefore the Tax engine must model at least:

```text
TaxRuleScope
├── country
├── tax_authority
├── tax_type
├── legal_reference
├── effective_from
├── effective_to
├── rule_version
└── source_provenance
```

The calculation kernel should carry only a neutral `rule_scope_id` or equivalent reference. It must not assume that `OHADA` is a sufficient tax jurisdiction.

## Non-negotiable invariants

1. Financial amounts use `Decimal`; floating-point values are rejected at the calculation-kernel boundary.
2. Every result has an explicit period and organization context.
3. Every result identifies its calculation definition and rule version.
4. Results can be `READY`, `NOT_READY`, `INCOMPLETE`, or `ERROR` with distinct semantics.
5. Dependency status is monotonic under `ERROR > NOT_READY > INCOMPLETE > READY`.
6. Unavailable source data must never be replaced with guessed values or zero.
7. Calculation results retain source references so a metric can be traced to authoritative records.
8. Calculation engines are read-side consumers unless a specific business workflow explicitly requires a persisted calculation artifact.
9. The accounting ledger remains the source of truth for posted accounting state.
10. Tenant isolation is part of the calculation context and must also be enforced by underlying queries.
11. Currency and rule-version context must match before financial results are combined or executed.
12. Tax rules require jurisdiction, effective dates and authoritative provenance before they can produce a tax result.
13. Profitability must not be calculated from a selected ledger slice whose POSTED journal-to-ledger reconciliation has detected drift.
14. Persisted profitability mappings must be tenant-scoped and rule-version scoped; ambiguous effective mappings must fail closed.
15. Profitability mapping writes must verify tenant ownership of the account and reject overlapping effective ranges; PostgreSQL enforces the non-overlap invariant transaction-safely.

## Implementation order

1. Harden the accounting kernel and fiscal closing controls.
2. Prove the minimal calculation kernel with a real profitability/P&L vertical slice.
3. Make the posted-ledger reporting surface explicitly period/date scoped and regression-test its query boundary.
4. Move only the abstractions required by that vertical slice into the shared kernel.
5. Consolidate existing profitability, KPI and variance work around the proven contracts.
6. Extend the Finance engine with working capital, liquidity and forecasting calculations.
7. Build Banking and Tax engines against real, validated source contracts.
8. Put AI analysis above verified calculation results; AI must not become the source of financial truth.

## Existing work to consolidate

FIP already has open work around profitability, variance, KPIs, working capital, liquidity and forecasting. These capabilities should be consolidated into the branch engines instead of duplicated. In particular, the existing `FinancialCalculationService` from the profitability work should be adapted into the first vertical slice rather than copied into a second calculation framework.
