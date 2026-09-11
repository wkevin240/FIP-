# Balance-sheet read model

FIP exposes the balance sheet as a read-only projection of the immutable posted ledger.

## Accounting boundary

The report does not infer account classes from account codes and does not embed OHADA or tax semantics. Each tenant must provide an explicit, versioned `ASSET`, `LIABILITY`, or `EQUITY` mapping with an effective date range.

The ledger adapter reads posted movements cumulatively through the report `end_date`. This is deliberate: a balance-sheet figure is a closing balance, not merely the movement inside the selected period.

For each mapped account:

- assets use `debit - credit`;
- liabilities and equity use `credit - debit`.

The calculation kernel then exposes `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, and `BALANCE_DIFFERENCE = ASSETS - LIABILITIES - EQUITY` with source posting provenance.

## Fail-closed behavior

- Missing category coverage produces `NOT_READY` rather than a zero.
- Overlapping effective mappings are rejected by the application and protected by the database uniqueness/range constraints where applicable.
- Cross-tenant account mappings are rejected before persistence.
- No data, mapping, opening balance, or accounting rule is seeded by this feature.

A zero `BALANCE_DIFFERENCE` is a mathematical integrity result for the selected mapped ledger slice; it is not a claim that an external accounting package or statutory report has been independently reconciled. External proof still requires authoritative source data.

## API

`GET /api/v1/accounting/balance-sheet`

Required: `start_date`, `end_date`.

Optional: `fiscal_period_id`, `rule_version`.

The endpoint is read-only and uses the existing `ledger:read` permission.
