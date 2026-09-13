# Journal immutability boundary

FIP treats a posted journal entry as an accounting fact that must not be rewritten behind the ledger.

## Invariants

- `DRAFT` journal entries may be changed by application workflows that explicitly support draft mutation.
- Once a journal entry is `POSTED`, its journal lines cannot be updated or deleted at the PostgreSQL boundary.
- A `POSTED` or `REVERSED` journal entry must retain `posted_at` and `posted_by` metadata.
- Once a journal entry is `REVERSED`, its original journal lines remain immutable.
- A `POSTED` or `REVERSED` journal entry cannot be deleted directly.
- Corrections are represented by a separate reversal journal entry rather than rewriting the original posting.

The database constraints and triggers are the final persistence boundary. Application validation remains necessary, but it is not treated as sufficient protection against direct SQL, maintenance tooling, or future application paths.

## Why this is required

Ledger postings are append-only. If the source journal lines could subsequently be changed or removed, the journal could disagree with the immutable ledger and the audit trail would no longer describe a stable accounting source event.

Posting metadata is part of the persisted state transition as well. A row cannot be `POSTED` without recording when it was posted and which actor performed the transition; this prevents a direct SQL path from manufacturing a posted state that lacks the metadata expected by the accounting service and audit trail.

The invariant therefore spans both layers:

```text
posted journal lines  ── immutable ──┐
posting metadata     ── required  ──┼──> immutable accounting history
ledger postings      ── immutable ──┘
```

Reversal is the controlled correction mechanism: it creates new ledger postings and preserves the original facts.

## Scope

This is a persistence-integrity invariant. It does not encode an OHADA classification, tax treatment, statutory retention period, or regulatory conclusion.

PostgreSQL integration tests exercise actual DML and verify the deployed constraint/trigger boundary. Test fixtures are transaction-scoped and are not production or seed data.
