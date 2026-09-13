# Journal-entry line account tenant boundary

FIP treats the account referenced by a journal-entry line as part of the same tenant boundary as the journal entry.

The application layer already selects accounts within the current organization. PostgreSQL now enforces the same invariant so a direct SQL writer cannot attach an account belonging to another organization to a journal entry.

## Database invariant

For every `journal_entry_lines` row:

`organization(journal_entry) = organization(account)`

Migration `20260913_0019` adds a trigger covering `INSERT` and changes to `journal_entry_id` or `account_id`.

The guard also preserves normal foreign-key behavior: the referenced journal entry and account must exist.

## Why this belongs at the persistence boundary

A journal line is a financial fact. Foreign keys prove that the journal and account exist, but separate foreign keys do not prove that both belong to the same organization.

The database trigger therefore complements service-level validation and prevents a cross-tenant accounting graph from being persisted through direct SQL or another future write path.

## Verification

`backend/tests/integration/test_journal_entry_line_account_tenant_postgres_integrity.py` runs after migrations against PostgreSQL and proves:

1. a cross-organization account is rejected with SQLSTATE `23514`;
2. a same-organization account is accepted;
3. changing a valid line to a cross-organization account is rejected;
4. the rejected mutation leaves the valid account reference unchanged.

The integration fixture is transaction-scoped and rolled back. It introduces no application seed data and encodes no OHADA or tax classification.
