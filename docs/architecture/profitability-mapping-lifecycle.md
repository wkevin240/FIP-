# Profitability Mapping Resolution

## Purpose

`ProfitabilityAccountMapping` is configuration, not accounting data. It classifies an account for a specific organization, `rule_version`, and effective date interval. The classification is never inferred from the account code.

## Calculation-window invariant

The current profitability kernel resolves one `ProfitabilityAccountRule` per account for a calculation execution. A calculation window that intersects more than one effective mapping for the same account therefore cannot be represented safely by that rule contract.

`LedgerProfitabilityService.calculate_from_persisted_mappings()` fails closed with `ProfitabilityMappingAmbiguityError` before reading the ledger when multiple persisted mappings for one account intersect the requested window.

This is intentional. It prevents FIP from silently choosing the older mapping, the newer mapping, or an arbitrary row when a mapping changes inside a reporting period.

The PostgreSQL exclusion constraint remains the lower-level invariant that prevents overlapping effective ranges for the same organization, account, and rule version. Non-overlapping historical mappings are valid configuration, but a calculation spanning a mapping boundary must be split into compatible calculation windows or handled by a future date-aware mapping contract before it can be calculated as one result.

## API boundary

The profitability mapping API exposes only tenant-scoped configuration operations:

- `GET /accounting/profitability/mappings` lists mappings intersecting an explicit period for an explicit `rule_version`;
- `POST /accounting/profitability/mappings` creates a mapping after validating account ownership, category, version, and effective dates.

The authenticated tenant supplies `organization_id`; clients cannot choose another organization. Mapping creation requires `profitability_mapping:create`, while read access is separate. Historical mappings are not overwritten through this API. A change is represented by a new effective interval, preserving the configuration history needed to explain a calculation.

## Missing configuration

An account with no persisted profitability mapping is not classified. Missing source coverage remains governed by the kernel's `NOT_READY` semantics rather than being converted to zero.

## Future extension boundary

Supporting a calculation window that legitimately crosses a mapping change requires the domain contract to carry effective dates on the account rules and the ledger facts to carry posting dates, followed by deterministic per-posting resolution. That change must be introduced as a separate, tested contract evolution; it must not be approximated by selecting one mapping for the whole window.
