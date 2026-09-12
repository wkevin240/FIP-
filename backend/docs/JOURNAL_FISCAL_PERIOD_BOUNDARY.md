# Journal / fiscal-period database boundary

FIP treats a fiscal-period close as a financial integrity boundary.

The application service already serializes journal mutations with the fiscal-period lock. The database must enforce the same boundary because direct SQL, background workers, migrations, or another service path can bypass application validation.

## Database invariant

A `journal_entries` row may only be inserted or moved/transitioned while its referenced fiscal period is `OPEN`.

The PostgreSQL trigger introduced by migration `20260912_0014` checks:

- the fiscal period belongs to the same organization as the journal entry;
- the fiscal period exists;
- the fiscal period status is `OPEN`.

The trigger covers `INSERT` and changes to `fiscal_period_id`, `organization_id`, or `status`.

## Why this is separate from service validation

Service-level checks provide useful API errors and domain validation. They are not sufficient as the final integrity boundary because a database connection can write directly to PostgreSQL.

The database guard therefore complements, rather than replaces, the service-level fiscal-period lock ordering.

## Reversals and closure

A reversal creates and posts a new journal entry. Posting requires the target fiscal period to remain open. Once the period is closed, the database boundary prevents a direct status transition to `POSTED`.

Closing a fiscal period changes the period row itself; the guard does not prevent the close operation. It prevents later journal mutations from bypassing that closed-period boundary.

## Verification

`backend/tests/integration/test_journal_fiscal_period_postgres_integrity.py` proves the trigger against a real PostgreSQL instance by checking both:

1. insertion of a journal directly into a closed period is rejected;
2. posting an existing draft after its period is closed is rejected and leaves the journal `DRAFT`.

The test uses a transaction/savepoint boundary for expected PostgreSQL errors and rolls back all fixture data.
