# Accounting controls

FIP treats the posted ledger as the authoritative financial movement layer.

## Journal entry lifecycle

`DRAFT -> POSTED`

A draft is mutable through the application layer. Posting requires:

- an organisation-scoped fiscal period;
- an open period;
- an entry date inside the period;
- active organisation-scoped accounts;
- at least two lines;
- exactly one side per line;
- non-negative monetary amounts;
- equal total debit and credit;
- no existing ledger posting for the entry.

Posting creates one immutable `LedgerPosting` per journal line and changes the journal status in the same database transaction.

## Idempotency

Financial commands carry an idempotency key scoped to the organisation. Reusing a key with a different canonical request payload is rejected with a conflict. This prevents retrying an API request from silently creating a second financial event.

## Reversal

A posted entry is never edited to undo its financial effect. The reversal command creates a new journal entry with the debit and credit sides swapped, posts that entry, and links it to the original through `reversal_of_id`.

Only one reversal is allowed for an original entry. A reversal requires an open fiscal period and a date inside that period. The original entry is then marked `REVERSED` for lifecycle visibility; its original ledger postings remain intact.

The current implementation intentionally does not pretend that reversal approval, segregation of duties, durable audit events, or cross-period reversal policy are complete. Those are separate control layers still required for production accounting operations.

## Period closing

A fiscal period can be closed only when:

- it is organisation-scoped and currently `OPEN`;
- no draft journal entries remain in the period;
- ledger debit and credit totals are equal.

Closing is not a substitute for a full period-end checklist. Bank reconciliation, subledger reconciliation, tax controls, review/approval and segregation of duties remain explicit future controls.
