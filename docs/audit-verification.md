# Audit chain verification

FIP exposes a read-only operational check for the durable, tenant-scoped audit chain.

## Endpoint

`GET /api/v1/accounting/audit/verify`

The endpoint requires the existing `audit:read` permission. It uses the authenticated tenant context; an organization identifier is never accepted from the caller as a substitute for that context.

The response reports:

- `organization_id`: the authenticated organization;
- `valid`: whether the persisted chain passes sequence and hash/link verification;
- `record_count`: the number of persisted audit records inspected.

An empty chain is considered structurally valid because there is no persisted record to verify. A non-empty chain must start at sequence 1, contain contiguous tenant-local sequence numbers, and pass the existing hash-chain verification.

This endpoint is an integrity control, not a statutory-compliance assertion. It does not provide retention certification, external timestamp anchoring, legal evidentiary certification, or OHADA/tax compliance by itself.
