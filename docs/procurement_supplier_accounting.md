# Procurement / Fournisseurs → Accounting

Le lot Procurement introduit un flux tenant-scopé pour les fournisseurs, les factures fournisseurs et les règlements fournisseurs. Les montants sont stockés et calculés exclusivement en `Decimal` avec une décomposition `HT + TVA = TTC`.

Une facture fournisseur est créée à l’état `DRAFT`, puis validée explicitement. La comptabilisation est une action séparée, déclenchée par l’utilisateur avec une clé `Idempotency-Key`. Le service réutilise `JournalEntryService`; aucun moteur comptable parallèle n’est introduit et aucune écriture n’est générée automatiquement lors de la simple création ou validation d’une facture.

Le profil comptable `ProcurementAccountingProfile` est obligatoire avant tout posting. Il doit être configuré par l’organisation avec un journal actif, un compte fournisseur, un compte de règlement et, lorsque la facture contient de la TVA, un compte de TVA déductible. Aucun compte ni taux de TVA n’est créé par migration ou par défaut.

Les opérations sensibles filtrent systématiquement `organization_id`. Les contraintes PostgreSQL utilisent des clés étrangères composites tenant-scopées. Les postings sont immuables, uniques par document et par clé d’idempotence, et l’Audit est écrit dans la même transaction que l’écriture comptable. Une période fiscale ouverte est obligatoire pour le posting d’une facture ou d’un règlement.

## API principale

| Méthode | Endpoint | Action |
|---|---|---|
| `POST` | `/api/v1/procurement/suppliers` | Créer un fournisseur |
| `POST` | `/api/v1/procurement/accounting-profile` | Configurer le profil comptable organisationnel |
| `POST` | `/api/v1/procurement/invoices` | Créer une facture fournisseur DRAFT |
| `POST` | `/api/v1/procurement/invoices/{id}/validate` | Valider explicitement la facture |
| `POST` | `/api/v1/procurement/invoices/{id}/post-accounting` | Comptabiliser avec `Idempotency-Key` |
| `POST` | `/api/v1/procurement/payments` | Créer un règlement fournisseur |
| `POST` | `/api/v1/procurement/payments/{id}/post-accounting` | Comptabiliser le règlement avec `Idempotency-Key` |

La migration `0023_procurement_invoices` dépend de `0022_bank_rules_accounting` et applique l’ownership `fip_accounting_owner` ainsi que les ACL minimales de `fip_user`.
