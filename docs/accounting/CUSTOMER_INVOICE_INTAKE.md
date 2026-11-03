# Customer invoice intake boundary

This increment records a customer invoice as a tenant-scoped source document and supports a controlled `DRAFT -> ISSUED` transition.

## Lifecycle

- Draft invoices may be created and edited by users with the matching customer-invoice permission.
- Issuance is an explicit action. The invoice creator cannot issue their own invoice.
- Issued invoices are immutable through this API. Corrections require a future credit-note workflow.
- Invoice number uniqueness is enforced within an organization.
- A composite customer foreign key prevents an invoice from referencing a customer in another organization.
- Material changes are appended to the tenant audit chain in the same transaction as the invoice mutation.

## Financial boundary

The API stores the provided subtotal, tax amount, total and three-letter currency code. It verifies `total = subtotal + tax` and date ordering. It does not calculate tax, validate a tax rate or currency against an authoritative registry, infer exchange rates, select accounting accounts, create a ledger posting, or calculate an outstanding balance. `ISSUED` means the source invoice was issued in FIP, not that accounting recognition has been posted or legally certified.

Endpoints are under `/api/v1/customer-invoices`: create, list/filter, read, update a draft, and issue a draft. The invoice lifecycle permissions are granted to owners, admins and accountants; managers and auditors have read access.

