# Controlled fiscal-period reopening

FIP treats period closure as a financial-control boundary. Reopening is therefore an explicit workflow rather than a generic status update.

## Contract

`POST /accounting/fiscal-periods/{period_id}/reopen` requires the dedicated `fiscal_period:reopen` permission and a non-blank reason (1–2000 characters).

The service locks the tenant-scoped fiscal-period row, accepts only a `CLOSED` period, changes it to `OPEN`, and writes `FISCAL_PERIOD_REOPENED` to the durable audit log in the same transaction.

A failed audit write rolls back the status change, so the reopen cannot succeed without its evidence record.

## Scope

This workflow does not assert that reopening is permitted by a particular OHADA or national regulatory regime. It provides the software control and evidence boundary needed for an authorized operational decision. Regulatory policy remains an external configuration/verification concern until an authoritative source is incorporated.

No business seed data is introduced.
