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

## Correction boundary

Once an entry is posted or reversed, its source lines are protected by the journal immutability boundary. Corrections must therefore be represented by a new reversal/corrective entry rather than by rewriting the historical source fact.

## Verification

`backend/tests/integration/test_journal_balance_postgres_integrity.py` runs against PostgreSQL after migrations. It proves both sides of the boundary:

1. an unbalanced draft cannot be transitioned to `POSTED` by direct SQL;
2. a balanced draft can be transitioned to `POSTED`.

The fixture transaction is rolled back and is not application business data.
