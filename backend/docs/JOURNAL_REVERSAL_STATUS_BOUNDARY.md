# Journal reversal status boundary

A journal entry marked `REVERSED` must have a corresponding reversal journal entry in the same organization whose status is `POSTED`.

Migration `20260913_0022` enforces this invariant in PostgreSQL with a deferred constraint trigger. Deferral allows the legitimate transactional sequence used by the application: create the reversal, post it, then mark the original entry `REVERSED` before the transaction commits.

The trigger also prevents a posted reversal from being changed away from `POSTED` while the original entry remains `REVERSED`. The tenant-scoped reversal foreign key from `20260913_0021` remains the underlying ownership boundary.

This is a persistence integrity control, not an OHADA interpretation. It does not determine when a reversal is legally or operationally authorized; that policy remains in the application workflow and external governance layer.

## Verification boundary

`test_journal_reversal_status_postgres_integrity.py` proves on the deployed PostgreSQL schema that:

- `REVERSED` is rejected when no posted reversal exists;
- a posted reversal permits the original to become `REVERSED`;
- a posted reversal cannot be downgraded while its original remains `REVERSED`;
- the trigger is deferred until transaction completion.

The integration fixture is transactional and rolled back; it creates no persistent business data.
