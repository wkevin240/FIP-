# FP&A — Budget versus réalisé

Ce lot ajoute un premier socle FP&A au-dessus du ledger Accounting central. Un budget appartient à une organisation et à un exercice fiscal existant. Il n’existe aucun budget, compte, période ou montant par défaut : toutes les lignes sont configurées explicitement par l’organisation.

## Workflow

| Étape | Règle |
|---|---|
| Création | Le budget est créé en `DRAFT` et associé à un exercice réel. Un seul budget est autorisé par exercice et organisation. |
| Lignes | Chaque ligne référence un compte et une période du même exercice par FK composites tenant-scopées. Les montants restent en `Decimal(18,2)`. |
| Approbation | Un budget sans ligne ne peut pas être approuvé. Après approbation, les lignes ne sont plus modifiables par le service. |
| Réalisé | Le réalisé est calculé exclusivement avec les lignes d’écritures `POSTED` du ledger central, filtrées par organisation, compte et période. Les écritures `DRAFT` ou `VOIDED` sont exclues. |
| Variance | `variance_amount = budget_amount - actual_amount`, avec validation Pydantic et Decimal. |

## API

| Méthode | Endpoint | Permission |
|---|---|---|
| `POST` | `/api/v1/accounting/budgets` | `budget:create` |
| `POST` | `/api/v1/accounting/budgets/{budget_id}/lines` | `budget:update` |
| `POST` | `/api/v1/accounting/budgets/{budget_id}/approve` | `budget:approve` |
| `GET` | `/api/v1/accounting/budgets/{budget_id}/variance` | `budget:read` |

La migration `0025_fpa_budgets` dépend de `0024_banking_control`. Elle crée les tables `budgets` et `budget_lines` avec propriétaire `fip_accounting_owner`, ACL minimales pour `fip_user`, contraintes d’état, unicité et clés étrangères composites organisation–exercice, organisation–période et organisation–compte.

Le calcul ne modifie jamais le ledger et ne produit aucune écriture comptable. Il s’agit d’une lecture analytique contrôlée du ledger existant.
