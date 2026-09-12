# Posted Journal Balance Invariant

FIP treats a posted journal entry as an immutable accounting fact. The application domain already validates double-entry lines before posting; PostgreSQL now enforces the same critical boundary when a journal entry is inserted or transitioned to `POSTED` or `REVERSED`.

## Database invariant

For an entry with status `POSTED` or `REVERSED`:

- at least one journal line must exist;
- total debit must equal total credit;
- total debit must be strictly positive.

The database trigger raises SQLSTATE `23514` when this invariant is violated.

## Why this exists

Application validation is necessary but is not the final integrity boundary. A direct SQL mutation, administrative script, migration mistake, or future service could otherwise mark an unbalanced entry as posted while bypassing the domain service.

This trigger does not encode an OHADA chart-of-accounts rule or tax rule. It protects the structural double-entry invariant that FIP's accounting domain already requires.

## Concurrency boundary

The balance check is only meaningful if journal-line mutations and the posting transition share the same database serialization point. The journal-line protection trigger therefore acquires a row lock on the parent `journal_entries` row before allowing a line mutation to proceed.

This creates one lock boundary for both operations:

- posting locks the parent journal row before checking its lines;
- line INSERT/UPDATE/DELETE locks the same parent journal row before changing source lines;
- a mutation racing with posting must wait for the parent-row lock and is re-evaluated against the journal status after the lock is acquired.

Without this serialization, two otherwise valid transactions could independently observe a balanced draft and a mutable line set and produce a posted journal whose final committed lines no longer matched the balance snapshot.

## Correction boundary

Once an entry is posted or reversed, its source lines are protected by the journal immutability boundary. Corrections must therefore be represented by a new reversal/corrective entry rather than by rewriting the historical source fact.

## Verification

`backend/tests/integration/test_journal_balance_postgres_integrity.py` runs against PostgreSQL after migrations. It proves both sides of the balance boundary:

1. an unbalanced draft cannot be transitioned to `POSTED` by direct SQL;
2. a balanced draft can be transitioned to `POSTED`.

`backend/tests/integration/test_journal_posting_immutability.py` also proves the parent-row locking behavior by holding the journal lock from a second PostgreSQL connection and verifying that a line mutation is blocked by the database lock timeout.

The integration fixtures are isolated test data and are removed or rolled back by the tests; they are not application business data.
