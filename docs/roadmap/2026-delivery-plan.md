# FIP delivery plan — December 2026

## Delivery objective

FIP is being developed as a Financial Operating System. The December 2026 delivery target is a production-oriented first release with a trustworthy accounting core and a deliberately bounded set of operational financial workflows. Unsupported modules must remain explicitly incomplete rather than presenting placeholders as finished functionality.

## September — hard financial core

- Stabilize tenant isolation, accounting invariants and migration integrity.
- Finish the posted journal → Ledger → controls → calculation path.
- Finish persisted, versioned profitability mappings.
- Make fiscal-period close readiness explicit and fail-closed.
- Keep the calculation kernel small and deterministic.
- Establish CI evidence for every release candidate.

## October — accounting operations

- Harden journal lifecycle, reversals and period boundaries.
- Complete general ledger and trial-balance reporting contracts.
- Build the first real Accounts Receivable and Accounts Payable vertical slices from authoritative domain records.
- Introduce closing workflow evidence rather than a simple CLOSED flag.
- Add audit/provenance links from financial results to source records.

## November — cash and financial operations

- Build treasury source contracts around bank accounts, transactions and reconciliation.
- Add cash position and liquidity calculations only from verified source data.
- Add management finance calculations that reuse the shared kernel rather than creating a second calculation framework.
- Establish integration boundaries for bank statements and external accounting imports.
- Start tax infrastructure only where the applicable legal source, jurisdiction, effective dates and provenance are available.

## December — release hardening

- Freeze the first-release scope.
- Run migration, security, tenant-isolation and regression suites against a clean PostgreSQL environment.
- Execute end-to-end workflows using authorized project data; do not create fictitious evidence to satisfy proof gates.
- Verify financial calculations independently where authoritative ledger data is available.
- Document known limitations and explicitly mark deferred modules.
- Produce a release candidate only when CI and migration checks are reproducible.

## Definition of done for the first release

A capability is release-ready only when:

1. its source of truth is identified;
2. tenant and period boundaries are enforced;
3. its domain invariants are encoded and tested;
4. persistence is protected by database constraints where appropriate;
5. calculations are deterministic and use `Decimal` for financial amounts;
6. failures are represented explicitly rather than converted into zeros;
7. source provenance is available for material financial results;
8. API authorization is enforced server-side;
9. migrations are reproducible from an empty database;
10. CI evidence exists for the release candidate;
11. regulatory rules have authoritative provenance before being encoded.

## Scope discipline

The December target does not justify implementing every FIP module superficially. Accounting, controls, reporting, receivables/payables and treasury foundations have priority over empty endpoints for payroll, inventory, fixed assets, tax or AI. A module without a complete source contract and proof path remains visibly incomplete.
