# Journal / fiscal-period database boundary

FIP treats a fiscal-period close as a financial integrity boundary.

The application service already validates that journal creation, posting, and reversal target an open fiscal period. PostgreSQL now enforces the same boundary so a direct SQL writer cannot bypass the lifecycle contract.

## Database invariant

A `journal_entries` row may only be inserted or changed while its referenced fiscal period is `OPEN`.

The PostgreSQL trigger introduced by migration `20260912_0015` checks:

- the fiscal period exists;
- the fiscal period belongs to the same organization as the journal entry;
- the fiscal period status is `OPEN`.

The trigger covers `INSERT` and changes to `fiscal_period_id`, `organization_id`, or `status`.

## Why this is separate from service validation

Service-level validation provides domain semantics and useful API errors. It is not sufficient as the final persistence boundary because direct SQL, maintenance tooling, or another future service path can bypass application code.

The database guard therefore complements the existing service-level fiscal-period row lock. It does not replace application validation.

## Closure behavior

Closing a fiscal period changes the period row itself. The guard does not prevent a legitimate close operation. After the status becomes non-`OPEN`, the database rejects direct journal insertion, period reassignment, organization reassignment, and status changes involving that period.

A reversal is a new journal entry and therefore also requires an open target period through the existing application workflow and database boundary.

## Verification

`backend/tests/integration/test_journal_fiscal_period_postgres_integrity.py` runs after migrations against a real PostgreSQL instance and proves:

1. inserting a journal directly into a closed period is rejected with SQLSTATE `23514`;
2. an existing draft journal cannot be posted after its period is closed;
3. the rejected posting leaves the journal in `DRAFT`.

The integration test uses savepoints for expected PostgreSQL errors and rolls back its fixture transaction. It does not create application seed data.
