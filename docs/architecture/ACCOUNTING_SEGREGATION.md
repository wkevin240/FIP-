# Journal Creator Segregation

FIP records the authenticated actor who creates a journal entry in `journal_entries.created_by`.

For new journal entries, the accounting service requires a different authenticated actor to perform the `POSTED` transition. The service returns HTTP 403 before creating ledger postings when the creator attempts to post the same entry.

PostgreSQL also protects the invariant with `trg_journal_creator_segregation`, so a direct SQL transition cannot bypass the application service. The database guard is intentionally limited to entries with a recorded `created_by`; the column is nullable because existing rows may predate this control and FIP does not invent historical authorship.

The recorded creator is immutable after the journal row is created. This prevents a caller from changing `created_by` on a draft and then posting as the newly assigned creator. PostgreSQL rejects such a mutation with SQLSTATE `42501`. Historical rows with no recorded creator remain nullable rather than being retroactively attributed.

Reversal is treated as a separate journal entry. The actor reversing an original entry must differ from the original entry's `created_by`. The reversal child itself is exempt from the self-post trigger because it is created and posted atomically by the reversal operation; otherwise every valid reversal would contradict the control by construction.

## Control boundary

This is a segregation-of-duties control for the journal lifecycle. It is not an approval workflow and does not claim statutory compliance. A later approval workflow can build on `created_by` and `posted_by` without rewriting historical journal authorship.

## Verification

The control is covered at two boundaries:

- unit service test: creator receives `403`, journal remains `DRAFT`, and no ledger postings are created;
- PostgreSQL integration test: direct creator mutation is rejected with SQLSTATE `42501`, direct self-posting is rejected with SQLSTATE `42501`, while a distinct posting actor is accepted.

Integration data is transaction-scoped test data only and is not application seed data.
