# Supplier invoice intake

FIP now has a tenant-scoped supplier-invoice intake boundary between supplier master data and future accounts-payable posting.

## Lifecycle

- `DRAFT`: invoice metadata and amounts can be edited.
- `APPROVED`: the captured invoice is approved for downstream AP processing; the record is no longer editable.
- `CANCELLED`: the invoice is withdrawn from the intake lifecycle and cannot be edited.

Approval and cancellation are explicit state transitions and are audited transactionally.

## Persistence invariants

- invoice numbers are unique per organization and supplier;
- supplier references are enforced by a composite `(organization_id, supplier_id)` foreign key;
- invoice date cannot be after due date;
- subtotal, tax amount and total amount cannot be negative;
- total amount must equal subtotal plus tax amount;
- the invoice status and provenance fields are persisted in PostgreSQL;
- mutations use row locking to serialize concurrent edits/transitions.

## Scope boundary

This module captures supplier invoice facts but does **not** post accounting entries, create payable balances, calculate taxes, select OHADA accounts, or determine statutory compliance. Those responsibilities require separate, verified domain rules and approval boundaries.

Amounts are stored as exact PostgreSQL `NUMERIC(20,2)` values. Currency is carried as a three-letter code and is not used here to infer tax treatment or exchange rates.

## Authorization

- accountants can create, read, update, approve and cancel supplier invoices;
- managers can read, approve and cancel;
- auditors can read only;
- unknown roles fail closed through the existing permission service.
