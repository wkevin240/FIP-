# FIP Calculation Architecture

## Decision

FIP uses a **shared calculation kernel plus one calculation engine per business branch**.

The shared kernel contains only cross-cutting calculation contracts. It must not contain accounting, banking, finance, or tax business rules.

```text
Financial Kernel
      |
      +-- Calculation contracts
      |     +-- Context
      |     +-- Definition
      |     +-- Result
      |     +-- Source provenance
      |     +-- Deterministic status
      |
      +-- Accounting Calculation Engine
      +-- Finance Calculation Engine
      +-- Banking Calculation Engine
      +-- Tax Calculation Engine
```

## Branch responsibilities

### Accounting Calculation Engine

Consumes authoritative posted accounting state and owns accounting-derived calculations such as account balances, trial balance, statement totals, depreciation and provisions when their underlying domain contracts exist.

### Finance Calculation Engine

Consumes validated accounting, treasury and operational facts. Owns management and financial analysis such as margins, profitability, working capital, liquidity ratios, DSO/DPO and variance analysis.

### Banking Calculation Engine

Consumes normalized banking transactions and reconciliation state. Owns bank balance, reconciliation difference, cash position and banking exposure calculations.

### Tax Calculation Engine

Consumes validated taxable facts and versioned tax rules. Owns tax bases, liabilities, reconciliation and declaration calculations. Tax rules must carry provenance and effective/version dates; rules must not be invented in application code.

## Non-negotiable invariants

1. Financial amounts use `Decimal`; floating-point values are rejected at the calculation-kernel boundary.
2. Every result has an explicit period and organization context.
3. Every result identifies its calculation definition and rule version.
4. Results can be `READY`, `NOT_READY`, or `INCOMPLETE`; unavailable source data must never be replaced with guessed values.
5. Calculation results retain source references so a metric can be traced back to authoritative records.
6. Calculation engines are read-side consumers unless a specific business workflow explicitly requires a persisted calculation artifact.
7. The accounting ledger remains the source of truth for posted accounting state.
8. Tenant isolation is part of the calculation context and must also be enforced by the underlying queries.

## Implementation order

1. Harden the accounting kernel and fiscal closing controls.
2. Introduce and test the shared calculation contracts.
3. Build the Accounting Calculation Engine against the posted ledger.
4. Adapt existing profitability, KPI and variance work to consume the Accounting/Finance calculation contracts rather than creating parallel calculations.
5. Add Banking and Tax engines only against real, validated source contracts.
6. Put AI analysis above verified calculation results; AI must not become the source of financial truth.

## Existing work to consolidate

FIP already has open work around profitability, variance, KPIs, working capital, liquidity and forecasting. These capabilities should be consolidated into the branch engines instead of duplicated. In particular, the existing `FinancialCalculationService` from the profitability work should be treated as an implementation candidate for the Finance/Accounting boundary, not copied into a second calculation framework.
