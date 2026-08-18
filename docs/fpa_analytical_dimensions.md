# FP&A — Dimensions analytiques et analyse du réalisé

Ce lot ajoute une couche analytique au-dessus du ledger Accounting sans modifier les montants ni l’historique des écritures. Les dimensions et leurs valeurs sont toujours configurées explicitement par organisation. Les migrations ne créent aucune dimension, valeur, compte ou donnée de démonstration.

## Modèle

| Objet | Règle |
|---|---|
| Dimension | Référentiel tenant-scopé identifié par un code organisationnel. |
| Valeur | Valeur active appartenant à une dimension et à la même organisation. |
| Allocation | Affectation positive d’une ligne d’écriture `POSTED` à une valeur analytique, avec montant `Decimal(18,2)` et clé d’idempotence. |
| Budget dimensionnel | Une ligne budgétaire peut désormais référencer une valeur analytique existante. Le workflow de budget reste celui de la PR #34. |

Une allocation ne modifie jamais `debit`, `credit`, le statut ou le contenu d’une écriture. Elle est refusée pour une écriture `DRAFT`, `VOIDED`, inexistante ou inter-tenant. Le montant cumulé des allocations d’une dimension ne peut pas dépasser le montant de la ligne comptable. La concurrence est sérialisée par verrou advisory transactionnel, compatible avec les ACL P0 du ledger.

## Reporting

Le endpoint `GET /api/v1/accounting/analytical/actuals` calcule, par dimension, valeur, compte et période : le montant alloué, le montant correspondant du ledger `POSTED` et l’écart de réconciliation. Lorsque la ligne budgétaire dimensionnelle correspondante existe dans un budget `APPROVED` ou `LOCKED`, le résultat expose également le budget et la variance budgétaire.

Le total analytique réconciliable est calculé à partir des mêmes lignes `POSTED` et du même périmètre organisationnel, période et compte. Les écritures non POSTED ne contribuent jamais au réalisé.

## API et permissions

| Méthode | Endpoint | Permission |
|---|---|---|
| `POST` | `/api/v1/accounting/analytical/dimensions` | `analytical_dimension:create` |
| `POST` | `/api/v1/accounting/analytical/dimensions/{dimension_id}/values` | `analytical_value:create` |
| `POST` | `/api/v1/accounting/analytical/allocations` | `analytical_allocation:create` |
| `GET` | `/api/v1/accounting/analytical/actuals` | `analytical_report:read` |

La migration `0026_fpa_analytical_dimensions` ajoute les tables analytiques, leurs FK composites tenant-scopées, l’extension dimensionnelle optionnelle des lignes budgétaires et les ACL PostgreSQL minimales. Elle dépend de `0025_fpa_budgets`.
