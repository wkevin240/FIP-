# Fiscal-year temporal integrity

FIP treats a fiscal year as a tenant-scoped accounting period. The application domain already rejects overlapping fiscal-year dates; PostgreSQL now enforces the same invariant at the persistence boundary.

## Database invariant

For a given organization, two fiscal years may not have overlapping date ranges.

Migration `20260913_0020` adds the GiST exclusion constraint `ex_fiscal_year_organization_no_overlap` using `btree_gist` for organization equality and `daterange` overlap detection.

The range is inclusive because fiscal-year dates are modeled as accounting calendar dates. Consecutive years such as `2026-01-01..2026-12-31` and `2027-01-01..2027-12-31` therefore remain valid.

## Why the database enforces it

A service-level overlap check is not sufficient under concurrent writes: two transactions can both observe the same empty interval and then insert conflicting fiscal years. PostgreSQL's exclusion constraint makes the invariant race-safe.

The constraint is tenant-scoped, so identical fiscal-year dates are allowed for different organizations.

## Verification

`backend/tests/integration/test_fiscal_year_postgres_integrity.py` runs after migrations against PostgreSQL and proves:

1. the exclusion constraint exists with the expected tenant/date dimensions;
2. overlapping fiscal years in one organization are rejected with SQLSTATE `23P01`;
3. non-overlapping fiscal years in one organization are accepted;
4. overlapping dates in different organizations are accepted;
5. an update that would create an overlap is rejected and the existing row remains unchanged.

The integration fixture is transaction-scoped and rolled back. It introduces no application seed data and encodes no OHADA or tax classification.
