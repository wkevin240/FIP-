# Journal entry date database boundary

FIP treats the relationship between a journal entry and its fiscal period as a persistence invariant.

The application service already validates that `entry_date` falls between the selected fiscal period's start and end dates. PostgreSQL now enforces the same rule so direct SQL writers cannot create or mutate a journal entry with a date outside its referenced period.

## Database invariant

For every `journal_entries` row:

`fiscal_period.start_date <= journal_entries.entry_date <= fiscal_period.end_date`

The database trigger introduced by migration `20260912_0016` checks the period selected by the journal entry's `fiscal_period_id` and `organization_id`.

The trigger covers `INSERT` and changes to `fiscal_period_id`, `organization_id`, or `entry_date`.

## Why this is separate from service validation

Service validation provides domain-level errors and user-facing behavior. It is not the final persistence boundary because SQL maintenance paths and future services can bypass application code.

The PostgreSQL guard complements the existing open-period and tenant-ownership guards; it does not replace the application validation.

## Verification

`backend/tests/integration/test_journal_entry_date_postgres_integrity.py` runs after migrations against PostgreSQL and proves:

1. a journal entry dated after the period end is rejected with SQLSTATE `23514`;
2. a journal entry dated on the period end boundary is accepted;
3. changing that valid entry to a date outside the period is rejected;
4. the rejected mutation leaves the original date unchanged.

The integration fixture is transaction-scoped and rolled back. It is not application seed data.
