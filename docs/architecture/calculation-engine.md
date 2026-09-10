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

The profitability formula slice is now implemented as `ProfitabilityCalculationEngine`. It consumes already-resolved category facts and computes Gross Profit, Operating Income, Net Income and margins through the shared DAG. It deliberately does **not** access the database or invent account mappings. The next integration step is to adapt the existing profitability service's posted-ledger query into these kernel inputs, rather than maintaining a second data-access implementation.

Only capabilities proven necessary by that vertical slice should be promoted into the kernel.

## Calculation status semantics

- `READY`: all dependencies are valid and the calculation produced a value.
- `NOT_READY`: a required business input is unavailable or not configured. This is a data/readiness condition, not a computational failure.
- `INCOMPLETE`: the calculation cannot be considered complete because required source coverage or reconciliation is incomplete.
- `ERROR`: the inputs were otherwise ready, but execution failed, for example an invalid operator result. A business engine may intentionally classify a known business condition such as a zero ratio denominator as `NOT_READY` instead of allowing it to become an arithmetic error.

A status must never be silently converted to zero. In particular, `NOT_READY` must propagate as `NOT_READY`, while an execution failure must remain `ERROR` so user-facing alerts and operational monitoring can distinguish missing data from a broken calculation.

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
5. Unavailable source data must never be replaced with guessed values or zero.
6. Calculation results retain source references so a metric can be traced to authoritative records.
7. Calculation engines are read-side consumers unless a specific business workflow explicitly requires a persisted calculation artifact.
8. The accounting ledger remains the source of truth for posted accounting state.
9. Tenant isolation is part of the calculation context and must also be enforced by underlying queries.
10. Tax rules require jurisdiction, effective dates and authoritative provenance before they can produce a tax result.

## Implementation order

1. Harden the accounting kernel and fiscal closing controls.
2. Prove the minimal calculation kernel with a real profitability/P&L vertical slice.
3. Move only the abstractions required by that vertical slice into the shared kernel.
4. Consolidate existing profitability, KPI and variance work around the proven contracts.
5. Extend the Finance engine with working capital, liquidity and forecasting calculations.
6. Build Banking and Tax engines against real, validated source contracts.
7. Put AI analysis above verified calculation results; AI must not become the source of financial truth.

## Existing work to consolidate

FIP already has open work around profitability, variance, KPIs, working capital, liquidity and forecasting. These capabilities should be consolidated into the branch engines instead of duplicated. In particular, the existing `FinancialCalculationService` from the profitability work should be adapted into the first vertical slice rather than copied into a second calculation framework.
