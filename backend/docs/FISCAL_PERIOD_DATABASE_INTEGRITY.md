# Fiscal-period database integrity

FIP treats fiscal-period structure as a persistence invariant, not only as an application validation concern.

## Invariants

For a `fiscal_periods` row, PostgreSQL now enforces that:

- the referenced fiscal year exists for the same organization;
- the period dates are contained within that fiscal year's start and end dates;
- periods in the same organization and fiscal year do not overlap.

The trigger is introduced by migration `20260912_0014` and covers inserts plus changes to the organization, fiscal year, or date boundaries.

## Concurrency model

The trigger locks the referenced fiscal-year row before checking for an overlapping period. The application service already locks the fiscal year while creating a period. Using the same parent-row serialization point prevents two concurrent writers from both passing an overlap check for the same fiscal year.

This is intentionally implemented without PostgreSQL extensions or exclusion constraints: the invariant can be enforced using the existing relational structure and a deterministic lock order.

## Verification

`backend/tests/integration/test_fiscal_period_postgres_integrity.py` runs against PostgreSQL after migrations and proves the deployed trigger definition plus rejection of:

1. an overlapping period;
2. a period outside the fiscal-year date range.

The test uses savepoints for expected PostgreSQL errors and rolls back its fixture transaction. It does not create business seed data.
