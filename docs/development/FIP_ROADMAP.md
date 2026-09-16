# FIP — Engineering Roadmap to Delivery

FIP is being developed as a Financial Operating System, not as a collection of CRUD screens. The delivery target is **31 December 2026**. The roadmap therefore prioritizes complete, verifiable vertical slices over breadth without executable business logic.

## Delivery principles

1. **Evolve continuously, but do not outrun the financial core.** Each new module must connect to the same tenant, accounting, control, audit and calculation foundations.
2. **Ship vertical slices.** A capability is valuable only when its domain rules, persistence, API, controls, tests and failure semantics work together.
3. **No fabricated proof.** Missing authoritative business data remains an explicit verification blocker; synthetic fixtures may test mechanics but never prove real-world accounting correctness.
4. **Regulatory provenance is mandatory.** OHADA accounting rules and national tax rules are versioned separately and are encoded only after verification against authoritative sources.
5. **December is a delivery date, not a reason to weaken invariants.** Scope is reduced before correctness is reduced.

## Target architecture

```text
Experience / API
       |
Application workflows
       |
Financial domains
  Accounting | AR/AP | Inventory | Assets | Treasury | Banking | Tax | Finance
       |
Controls + Audit + Workflow
       |
Shared deterministic Calculation Kernel
       |
Financial source of truth
  Journal -> POSTED Ledger -> verified facts
       |
PostgreSQL / integrations / documents
```

The kernel is shared infrastructure for deterministic financial calculations. Domain engines own their business semantics. AI remains above verified financial facts and cannot bypass authorization or accounting controls.

## Delivery sequence

### September 2026 — Accounting core and architecture stabilization

- [x] Tenant-aware accounting reads
- [x] Journal-entry invariants and posting model
- [x] Immutable ledger postings
- [x] Trial balance and general ledger
- [x] Journal-to-ledger reconciliation
- [x] Period/date validation
- [x] Deterministic Calculation Kernel with Decimal arithmetic
- [x] Explicit profitability mappings with rule version and effective dates
- [x] Ledger -> profitability facts -> P&L orchestration
- [x] Read-only profitability API
- [x] Period close gated by ledger integrity
- [ ] Resolve and merge the calculation-kernel branch cleanly into the accounting hardening line
- [x] Controlled period reopening with mandatory reason and audit trail
- [x] Durable audit-event persistence
- [x] Accounting API integration verification against PostgreSQL migrations

### October 2026 — First operational financial slices

Priority is executable business capability, not empty module scaffolding.

- [x] Customer master data foundation
- [ ] Customer receivables lifecycle
- [ ] Supplier master data and payables lifecycle
- [ ] Invoice -> accounting entry boundary
- [ ] Payment -> allocation -> ledger boundary
- [ ] Bank transaction import boundary
- [ ] Bank reconciliation matching and exception workflow
- [ ] Period-end control checklist
- [ ] Role separation for create / approve / post / reverse / close

Each slice must reuse the existing ledger, tenant, audit and calculation boundaries rather than introduce parallel financial state.

### November 2026 — Financial operations and regulatory foundation

- [ ] Fixed-asset lifecycle and depreciation calculation boundary
- [ ] Inventory movement and valuation boundary
- [ ] Treasury cash position and cash forecasting primitives
- [ ] Financial statement foundation: P&L, balance sheet and cash-flow projections where source coverage is sufficient
- [ ] Tax-rule model: jurisdiction, authority, tax type, legal reference, effective dates, version and provenance
- [ ] First verified Cameroon tax rules only after official-source review
- [ ] Regulatory/audit evidence model
- [ ] Reporting exports with traceable source references

### December 2026 — Integration, proof and release hardening

- [ ] End-to-end authentication and tenant-isolation verification
- [ ] PostgreSQL migration upgrade/downgrade verification
- [ ] Financial-control regression suite
- [ ] Reconciliation regression suite
- [ ] API contract and authorization regression suite
- [ ] Production deployment and recovery checks
- [ ] Performance checks on representative data volumes
- [ ] Independent accounting verification of supported financial statements
- [ ] Authoritative grand-ledger/Sage comparison when an authorized real ledger is available
- [ ] Release documentation and operational runbook
- [ ] Final scope review: unsupported capabilities remain explicitly marked NOT_READY rather than presented as complete

## Definition of done for a financial capability

A financial feature is not complete merely because an endpoint returns HTTP 200. It must have:

- Domain invariants expressed in code
- Tenant and authorization boundaries
- Deterministic monetary arithmetic
- Transactional persistence where multiple records must change together
- Negative-path and authorization tests
- Auditability for material mutations
- Explicit status and failure semantics
- Migration coverage where persistence changes
- Documentation of assumptions and regulatory sources
- CI verification before merge
- An explicit proof status distinguishing tested mechanics from verified accounting outcomes

## Release gates

### Gate A — Financial correctness

No known violation of double-entry, ledger immutability, period boundaries, tenant isolation or deterministic calculation contracts.

### Gate B — Operational completeness

The supported December scope must execute real workflows from business transaction to accounting state and reporting result, rather than exposing disconnected CRUD endpoints.

### Gate C — Evidence

Every material financial result must be traceable to its source transactions, rules and calculation version. Where external authoritative evidence is required but unavailable, FIP must say so explicitly.

### Gate D — Production readiness

CI, migrations, authorization, audit, recovery and deployment checks must be verifiable before release.

## Current focus

The current branch is completing the accounting financial core. The next work should move outward into operational slices while continuing to strengthen the shared controls and kernel. Avoid adding generic abstractions that do not unlock a concrete December delivery capability.
