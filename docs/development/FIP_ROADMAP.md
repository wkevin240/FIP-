# FIP — Engineering Roadmap

FIP is being developed as a financial operating system, not as a collection of CRUD screens. Every accounting mutation must preserve financial invariants, tenant isolation, traceability and deterministic calculations.

## North-star capabilities

1. **Accounting ledger**
   - Immutable journal posting
   - Double-entry enforcement
   - Journals, fiscal years and periods
   - Period locking and controlled reopening
   - General ledger and trial balance
   - Account balances and account statements

2. **Auditability**
   - Actor, organization and request context
   - Tamper-evident audit chain
   - Domain events for side effects
   - No silent mutation of posted accounting records

3. **Financial operations**
   - Customer and supplier invoicing
   - Receivables and payables
   - Payments and allocations
   - Bank accounts and reconciliation
   - Fixed assets and depreciation
   - Tax calculation and reporting

4. **African/OHADA readiness**
   - Treat the official applicable accounting and tax texts as the source of truth
   - Keep regulatory rules versioned and testable
   - Separate generic accounting mechanics from jurisdiction-specific rules
   - Never hard-code an unverified tax rate or regulatory claim

5. **Enterprise controls**
   - Multi-organization isolation
   - RBAC and least privilege
   - Idempotency for financial commands
   - Optimistic/concurrency safeguards where needed
   - Structured audit logs
   - Production readiness checks

6. **AI layer — after the ledger is trustworthy**
   - Explain transactions and anomalies
   - Assist reconciliation
   - Classify source documents with human approval
   - Detect unusual postings
   - Generate management insights
   - Never allow an AI suggestion to bypass accounting invariants or authorization

## Development order

### Phase 1 — Accounting kernel

- [x] Tenant-aware account API
- [x] Account hierarchy safeguards
- [x] Journal-entry domain invariants
- [x] Decimal-based accounting calculations
- [x] Tamper-evident audit record primitive
- [x] Domain event primitive
- [ ] Persisted journal posting transaction
- [ ] Fiscal-period posting guard
- [ ] Idempotency key for financial commands
- [ ] Trial balance query
- [ ] General ledger query

### Phase 2 — Controls and reconciliation

- [ ] Period close state machine
- [ ] Controlled reopening with audit trail
- [ ] Bank statement import boundary
- [ ] Reconciliation matching engine
- [ ] Unreconciled-items workflow

### Phase 3 — Commercial modules

- [ ] Customers and suppliers
- [ ] Invoices and credit notes
- [ ] Payments and allocations
- [ ] Tax-rule engine
- [ ] Inventory valuation hooks
- [ ] Fixed-asset depreciation engine

### Phase 4 — Financial intelligence

- [ ] Cash-flow analytics
- [ ] Working-capital analytics
- [ ] Margin and profitability views
- [ ] Anomaly detection
- [ ] Explainable accounting assistant

## Definition of done for financial code

A financial feature is not considered complete merely because an endpoint returns HTTP 200. It must have:

- Domain invariants expressed in code
- Organization/authorization boundaries
- Deterministic monetary arithmetic
- Transactional persistence where multiple records must change together
- Negative-path tests
- Auditability for material mutations
- Clear failure semantics
- Documentation of assumptions and regulatory sources
- CI verification before merge

## Current rule

Prefer a smaller correct accounting kernel over a larger collection of disconnected features. Build the ledger first; build automation and AI on top of trustworthy financial state.
