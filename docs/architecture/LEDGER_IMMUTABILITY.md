# Ledger immutability

`ledger_postings` is the authoritative persisted representation of posted accounting movements. The application model already treats these rows as immutable; the database now enforces the same boundary.

## Invariant

A ledger posting is created from a posted journal line and cannot subsequently be updated or deleted. Corrections must therefore be represented by a new accounting transaction (for example, a reversal) rather than mutation of historical posting data.

## Enforcement

Migration `20260912_0010` installs two PostgreSQL `BEFORE` triggers on `ledger_postings`:

- `trg_ledger_postings_no_update`
- `trg_ledger_postings_no_delete`

Both invoke `fip_ledger_postings_append_only()` and reject the mutation with SQLSTATE `55000`.

This is a persistence invariant, not a regulatory classification. No OHADA or tax rule is encoded by this migration.

## Verification

The PostgreSQL integration suite verifies the trigger definitions using `pg_get_triggerdef()`. It does not insert fictitious accounting data or treat a skipped PostgreSQL environment as a successful integration proof.
