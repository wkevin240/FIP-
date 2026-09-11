# Balance-sheet read model

FIP exposes the balance sheet as a read-only projection of the immutable posted ledger.

## Accounting boundary

The report does not infer account classes from account codes and does not embed OHADA or tax semantics. Each tenant must provide an explicit, versioned `ASSET`, `LIABILITY`, or `EQUITY` mapping with an effective date range.

The ledger adapter reads posted movements cumulatively through the report `end_date`. This is deliberate: a balance-sheet figure is a closing balance, not merely the movement inside the selected period.

Mapping selection follows the same point-in-time rule: persisted classifications are selected **as effective on the report `end_date`**. A mapping that ended before that snapshot is historical configuration and must not be mixed with the current closing classification simply because it overlaps the broader reporting period. If more than one effective mapping is returned for the same account, the calculation fails closed as ambiguous.

For each mapped account:

- assets use `debit - credit`;
- liabilities and equity use `credit - debit`.

The calculation kernel then exposes `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, and `BALANCE_DIFFERENCE = ASSETS - LIABILITIES - EQUITY` with source posting provenance.

## Fail-closed behavior

- Missing category coverage produces `NOT_READY` rather than a zero.
- Overlapping effective mappings are rejected by the application **and** by a PostgreSQL GiST exclusion constraint scoped to organization, account, rule version, and effective date range.
- Cross-tenant account mappings are rejected before persistence.
- Snapshot ambiguity is rejected rather than resolved by ordering or recency heuristics.
- No data, mapping, opening balance, or accounting rule is seeded by this feature.

The application-level overlap check provides an early deterministic error for ordinary requests; the PostgreSQL exclusion constraint is the authoritative concurrency guard so two concurrent writers cannot bypass the invariant between the read check and commit.

A zero `BALANCE_DIFFERENCE` is a mathematical integrity result for the selected mapped ledger slice; it is not a claim that an external accounting package or statutory report has been independently reconciled. External proof still requires authoritative source data.

## API

`GET /api/v1/accounting/balance-sheet`

Required: `start_date`, `end_date`.

Optional: `fiscal_period_id`, `rule_version`.

The endpoint is read-only and uses the existing `ledger:read` permission.
