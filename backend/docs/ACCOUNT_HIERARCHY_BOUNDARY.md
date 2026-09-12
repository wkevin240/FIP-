# Account hierarchy database boundary

FIP treats an account's hierarchy references as tenant-scoped persistence invariants.

The application service already resolves `parent_id` and `collective_account_id` through the authenticated organization. PostgreSQL now enforces the same boundary so direct SQL writers cannot attach an account to a hierarchy object owned by another organization.

## Database invariants

For every `accounts` row:

- `parent_id`, when present, references an account in the same organization;
- `collective_account_id`, when present, references an account in the same organization;
- an account cannot reference itself as its parent;
- an account cannot reference itself as its collective account.

Migration `20260912_0018` enforces these rules on `INSERT` and on changes to `organization_id`, `parent_id`, or `collective_account_id`.

## Why this is a database boundary

The service layer provides domain-level errors and hierarchy construction. It is not sufficient as the final persistence boundary because maintenance SQL, future integrations, or another service path can bypass the Python service.

The trigger complements the existing foreign keys. The individual foreign keys prove that the referenced account exists; the trigger additionally proves that the relationship does not cross tenant boundaries.

This migration deliberately does not attempt to encode the complete accounting classification or OHADA chart of accounts. Account classification remains organization-specific until an authoritative regulatory mapping is explicitly introduced and verified.

## Verification

`backend/tests/integration/test_account_hierarchy_postgres_integrity.py` runs after migrations against PostgreSQL and proves:

1. a parent account from another organization is rejected with SQLSTATE `23514`;
2. a collective account from another organization is rejected;
3. a self-parent reference is rejected;
4. a valid same-organization hierarchy is accepted.

The integration fixture is transaction-scoped and rolled back. It is not application seed data.
