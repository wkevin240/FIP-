# Accounting lifecycle RBAC boundary

FIP keeps the high-impact accounting lifecycle behind explicit permissions. The policy is intentionally fail-closed for roles that are not listed in the permission matrix.

## Current policy

| Role | Core accounting reads | Create/update journal | Post journal | Reverse journal | Close period | Reopen period |
| --- | --- | --- | --- | --- | --- | --- |
| Owner | Yes | Yes | Yes | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes | Yes | Yes | Yes |
| Accountant | Yes | Yes | Yes | No | No | No |
| Manager | Yes | No | No | No | No | No |
| Auditor | Yes | No | No | No | No | No |
| User | No | No | No | No | No | No |

`journal_entry:reverse`, `fiscal_period:close`, and `fiscal_period:reopen` are deliberately not granted to the accountant role at this stage. FIP does not yet have a separate approval workflow that would justify granting those lifecycle transitions to a broader operational role.

This document describes the implemented authorization policy; it is not a claim about statutory segregation-of-duties requirements in any particular jurisdiction.

## Enforcement

The API derives the organization and user from the authenticated tenant context and applies `require_permission(...)` to accounting mutation endpoints. The permission service grants only the permissions declared for the caller's role, with the existing owner/admin and explicit superuser override.

The unit suite locks the critical lifecycle boundary so accidental permission expansion is detected before merge.

## Scope boundary

This is an authorization/control hardening increment. It does not add accounting data, chart-of-account mappings, tax rules, OHADA classifications, or approval records.
