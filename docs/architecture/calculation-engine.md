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

## Accounting reporting boundary

The accounting read side derives reporting exclusively from immutable `LedgerPosting` rows. The reporting endpoints support three explicit filters:

- `fiscal_period_id` for an organization-owned fiscal period;
- `start_date` as an inclusive posting-date lower bound;
- `end_date` as an inclusive posting-date upper bound.

A supplied fiscal-period identifier is tenant-validated before it is used. When a period is selected, explicit dates must remain inside that period. Date ranges reject `start_date > end_date`. Without filters, the existing all-postings behavior is preserved for backward compatibility.

This layer does not reconstruct draft journal entries and does not silently include unposted state. Account balances and trial balance totals remain projections of the selected posted movements.

For an account movement report, a partial range now exposes an explicit `opening_balance` computed from postings before `start_date`, then applies only movements inside the requested range. `closing_balance` is the resulting cumulative balance. This prevents a partial-range running balance from being mistaken for an opening balance. When no `start_date` is supplied, the opening balance is zero because the selected result begins at the first available posting under the supplied filters.

## Posting reconciliation control

The accounting read side also exposes a reconciliation control between non-draft journal lines and immutable ledger postings. For a selected organization and optional period/date scope, it reports:

- expected non-draft journal-line count;
- actual ledger-posting count;
- missing postings;
- orphan postings;
- postings whose account, debit, credit or fiscal-period identity differs from the journal line.

`is_reconciled` is true only when all three discrepancy sets are empty. This is a detection control: it does not mutate either side or manufacture a correction. A reconciliation failure must remain visible to downstream reporting and calculation consumers rather than being silently treated as balanced.

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
        +--> FIP posted-ledger extraction --> kernel DAG --> P&L result
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
11. Tax rules require jurisdiction, effective dates and authoritative provenance before they can produce a tax result.

## Implementation order

1. Harden the accounting kernel and fiscal closing controls.
2. Prove the minimal calculation kernel with a real profitability/P&L vertical slice.
3. Make the posted-ledger reporting surface explicitly period/date scoped and regression-test its query boundary.
4. Add ledger-to-journal reconciliation controls and feed reconciliation state into calculation readiness.
5. Move only the abstractions required by that vertical slice into the shared kernel.
6. Consolidate existing profitability, KPI and variance work around the proven contracts.
7. Extend the Finance engine with working capital, liquidity and forecasting calculations.
8. Build Banking and Tax engines against real, validated source contracts.
9. Put AI analysis above verified calculation results; AI must not become the source of financial truth.

## Existing work to consolidate

FIP already has open work around profitability, variance, KPIs, working capital, liquidity and forecasting. These capabilities should be consolidated into the branch engines instead of duplicated. In particular, the existing `FinancialCalculationService` from the profitability work should be adapted into the first vertical slice rather than copied into a second calculation framework.
