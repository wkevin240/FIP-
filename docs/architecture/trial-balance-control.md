# Trial Balance Integrity Control

FIP exposes a read-only trial-balance control over the same immutable `LedgerPosting` rows used by the accounting reporting surface.

## Contract

The control receives already-resolved trial-balance rows and computes, using `Decimal` values only:

- number of reported account rows;
- total debit;
- total credit;
- debit minus credit difference;
- `is_balanced`.

No tolerance, rounding adjustment, zero substitution, correction posting or mutation is performed.

## API

`GET /trial-balance/control`

The endpoint accepts the same optional `fiscal_period_id`, `start_date` and `end_date` scope as `GET /trial-balance`, and applies the control to that exact result set.

A non-zero difference is therefore an explicit integrity exception for the selected posted-ledger scope. The control does not prove that the underlying journal-to-ledger relationship is correct by itself; that is the responsibility of `/reconciliation`, which checks POSTED journal lines against immutable ledger postings.

Together, the two controls provide distinct guarantees:

```text
POSTED journal lines
       |
       +--> journal-to-ledger reconciliation
       |          |
       |          +--> missing / orphan / mismatch
       |
       +--> immutable LedgerPosting rows
                  |
                  +--> trial balance
                             |
                             +--> debit/credit integrity control
```

No OHADA classification is required for this control because it does not interpret account classes; it verifies the double-entry totals of the selected ledger projection.
