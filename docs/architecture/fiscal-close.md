# Fiscal period closing architecture

FIP treats fiscal-period closing as a source-integrity gate, not as a UI status change.

## Readiness contract

`GET /accounting/fiscal-periods/{period_id}/close-readiness` evaluates an open period without mutating it. The response exposes:

- draft journal-entry count;
- POSTED journal-line to ledger-posting reconciliation;
- exact trial-balance debit/credit control;
- a single `ready_to_close` decision derived from those controls.

The authenticated tenant supplies the organization scope. The caller cannot choose another organization in the request.

## Closing sequence

```text
OPEN fiscal period
       |
       +--> no DRAFT journal entries
       |
       +--> POSTED journal lines reconcile with LedgerPosting
       |
       +--> trial balance is exactly balanced
       |
       +--> ready_to_close
       |
       +--> CLOSED
```

Any failed control blocks the transition with HTTP 409. The service does not create correcting entries, ignore drift, or substitute missing values.

## Why reconciliation comes before balance

A ledger can be mathematically balanced while still being incomplete or inconsistent with the POSTED journal source. Therefore `debit == credit` is necessary but not sufficient. FIP requires both source reconciliation and balance before closing.

## No regulatory assumptions

This workflow encodes an application integrity control only. It does not claim that these checks are a complete statutory closing procedure for OHADA or any national tax regime. Jurisdiction-specific requirements must be added separately with authoritative legal provenance and effective dates.
