# Fiscal-period mutation serialization

A fiscal period is a transaction boundary for accounting mutations.

## Invariant

Closing a fiscal period acquires a PostgreSQL row lock on the period. Journal creation, posting, and reversal acquire the same row lock before validating that the period is open.

This creates one serialization point for the lifecycle:

```text
journal create ─┐
journal post ───┼──> fiscal_period row lock
journal reverse ┘
                         │
                    close readiness
                         │
                    status transition
                         │
                       commit
```

Without the shared lock, close-readiness could observe a balanced/reconciled period while a concurrent journal mutation had already passed its `OPEN` check but had not committed yet. The mutation could then commit after the readiness snapshot.

The lock does not add any accounting rule or regulatory interpretation. It only makes the existing state-transition contract serializable at the fiscal-period boundary.

## Scope

- PostgreSQL row-level locking via `SELECT ... FOR UPDATE`.
- Tenant and period identifiers remain part of every lookup.
- No business seed or demonstration data is required.
- The invariant must be exercised against PostgreSQL in integration coverage before being treated as operationally validated.
