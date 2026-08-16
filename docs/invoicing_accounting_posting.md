# Intégration Facturation → Accounting

## Objet et périmètre

Cette intégration comptabilise une **facture déjà émise** au moyen du service Accounting existant. Elle ne crée ni facture, ni client, ni compte, ni journal, ni période, ni écriture de démonstration. Les comptes et le journal doivent être configurés par l’organisation avant toute comptabilisation.

Le lot couvre uniquement la facture émise. Les avoirs, encaissements, mouvements de stock, paie, immobilisations, TVA déclarative et trésorerie conservent leurs flux propres et ne sont pas modifiés ici.

## Configuration requise

Chaque organisation configure un unique profil actif contenant un journal de ventes, un compte de créance client de type `ASSET`, un compte de produits de type `REVENUE` et, si des factures sont taxées, un compte de TVA collectée de type `LIABILITY`. PostgreSQL impose que chacun de ces objets appartient à la même organisation que le profil.

| Route | Permission | Effet |
|---|---|---|
| `GET /api/v1/invoicing/invoices/accounting-profile` | `invoice:read` | Lit le profil existant. |
| `POST /api/v1/invoicing/invoices/accounting-profile` | `invoice:accounting:configure` | Crée le profil tenant-scopé après validation des comptes actifs et de leurs types. |
| `POST /api/v1/invoicing/invoices/{invoice_id}/post-accounting` | `invoice:post` | Comptabilise une facture émise à l’aide d’une clé d’idempotence obligatoire. |

> En l’absence de profil actif, de journal actif, de comptes actifs ou de période couvrant la date de facture, FIP retourne une erreur métier explicite. Il ne sélectionne jamais un compte ou une période par défaut.

## Écriture générée

Pour une facture émise et positive, le flux repose exclusivement sur `Decimal` :

| Mouvement | Montant |
|---|---:|
| Débit — créance client | TTC |
| Crédit — produit | HT |
| Crédit — TVA collectée, si TVA positive | TVA |

L’écriture est construite par `JournalEntryService`, puis comptabilisée par ses protections de période, de comptes actifs, d’équilibre et de transition PostgreSQL. Les écritures `POSTED` restent immuables ; toute correction comptable doit utiliser les mécanismes Accounting de contre-passation et de correction.

## Atomicité, idempotence et traçabilité

La facture est verrouillée avant traitement. La liaison `invoice_accounting_postings` porte `organization_id`, `source_module`, `source_type`, `source_id`, `journal_entry_id`, `idempotency_key` et `status`. Elle comporte des unicités PostgreSQL qui empêchent une seconde comptabilisation de la même facture ainsi qu’une réutilisation d’une même clé sur une autre facture.

La création de l’écriture, sa comptabilisation, la liaison source et l’événement Audit `INVOICE_POSTED_TO_ACCOUNTING` sont préparés dans la même transaction. En cas d’échec, aucun lien de comptabilisation, aucune écriture et aucune trace Audit métier de facture ne sont conservés. Les appels concurrents sur la même facture sont sérialisés par le verrou de la facture et renvoient la liaison existante une fois la première transaction validée.

## États et limites

Une facture `DRAFT` ne peut pas être comptabilisée, une facture `CANCELLED` est refusée et une période `CLOSED` ou `LOCKED` est refusée. Une facture avec TVA requiert un compte de TVA collectée configuré. Les montants nuls sont refusés car une écriture Accounting doit comporter des lignes débit/crédit strictement non nulles.
