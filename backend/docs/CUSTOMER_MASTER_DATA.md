# Customer master data boundary

FIP customer master data is organization-scoped and is a source boundary for future receivables workflows. This increment does not create invoices, payments, tax calculations, or accounting entries.

## Persistence invariants

- `organization_id` scopes every customer read and mutation.
- `code` is unique within an organization and cannot contain whitespace.
- `tax_id`, when provided, is unique within an organization.
- `legal_name` cannot be blank at the database boundary.
- `created_by` and `updated_by` reference real users; they are never inferred from request payloads.
- customer creation and updates append durable tenant audit events in the same transaction as the master-data mutation.
- deletion is intentionally not exposed; deactivation uses `is_active=false` so historical references can remain stable.

## Authorization

- `customer:create` and `customer:update` are granted to accountants and administrative roles.
- `customer:read` is granted to accountants, managers, auditors and administrative roles.
- unknown roles fail closed through the existing permission service.

## Verification boundary

The unit suite verifies normalization, tenant scoping, duplicate rejection and audit transaction behavior. PostgreSQL CI verifies that the table, unique/check constraints and foreign keys are actually deployed after migrations.

This document makes no OHADA or tax classification claim. Those rules remain separate and require authoritative-source verification before encoding.
