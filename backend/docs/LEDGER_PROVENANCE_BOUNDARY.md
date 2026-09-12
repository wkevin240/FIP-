# Ledger source provenance database boundary

FIP treats a ledger posting as an immutable accounting movement derived from one exact journal-entry line. The foreign keys alone prove that referenced rows exist, but they do not prove that their tenant, period, account, date, amount, or status agree.

Migration `20260912_0017` adds a PostgreSQL trigger for that missing persistence boundary.

## Database invariant

For every inserted `ledger_postings` row:

- the referenced journal entry and journal line must exist together;
- the journal entry must be `POSTED`;
- `organization_id` must match the journal entry;
- `fiscal_period_id` must match the journal entry;
- `account_id` must match the source journal line;
- `posting_date` must equal the journal entry date;
- `line_number` must equal the source line number;
- `debit` and `credit` must equal the source line amounts.

The guard applies only to `INSERT` because ledger postings are already protected by append-only UPDATE/DELETE triggers.

## Why this is a database invariant

Application services create ledger postings from journal lines and already populate these fields from the same source. That is the normal path, but it is not sufficient as a persistence boundary: direct SQL, maintenance scripts, or another service can otherwise create a structurally valid foreign-key graph whose accounting facts disagree with the source journal.

The trigger therefore provides defense in depth. It does not replace the application/domain validation or the existing ledger append-only control.

## Tenant isolation

The trigger explicitly compares the posting organization with the source journal organization. PostgreSQL foreign keys on the individual identifiers do not, by themselves, enforce that all accounting objects belong to the same organization.

## Verification

`backend/tests/integration/test_ledger_provenance_postgres_integrity.py` runs after migrations against PostgreSQL and proves:

1. a posting for a `DRAFT` journal is rejected with SQLSTATE `23514`;
2. a cross-organization source/provenance mismatch is rejected;
3. an amount mismatch against the source line is rejected;
4. an exact posting derived from a `POSTED` journal line is accepted.

The integration fixture is transaction-scoped and rolled back. It is not application seed data.
