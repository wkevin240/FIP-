# Journal immutability boundary

FIP treats a posted journal entry as an accounting fact that must not be rewritten behind the ledger.

## Invariants

- `DRAFT` journal entries may be changed by application workflows that explicitly support draft mutation.
- Once a journal entry is `POSTED`, its journal lines cannot be updated or deleted at the PostgreSQL boundary.
- Once a journal entry is `REVERSED`, its original journal lines remain immutable.
- A `POSTED` or `REVERSED` journal entry cannot be deleted directly.
- Corrections are represented by a separate reversal journal entry rather than rewriting the original posting.

The database triggers are the final persistence boundary. Application validation remains necessary, but it is not treated as sufficient protection against direct SQL, maintenance tooling, or future application paths.

## Why this is required

Ledger postings are append-only. If the source journal lines could subsequently be changed or removed, the journal could disagree with the immutable ledger and the audit trail would no longer describe a stable accounting source event.

The invariant therefore spans both layers:

```text
posted journal lines  ── immutable ──┐
                                    ├──> immutable accounting history
ledger postings      ── immutable ──┘
```

Reversal is the controlled correction mechanism: it creates new ledger postings and preserves the original facts.

## Scope

This is a persistence-integrity invariant. It does not encode an OHADA classification, tax treatment, statutory retention period, or regulatory conclusion.

PostgreSQL integration tests exercise actual `UPDATE` and `DELETE` statements and require SQLSTATE `55000` from the protection triggers. Test fixtures are transaction-scoped and are not production or seed data.
