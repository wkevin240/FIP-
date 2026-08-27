# Financial KPI & Management Control Engine

## Positionnement

Le KPI Engine est une couche de contrôle en lecture seule au-dessus de `FinancialCalculationService`. Il ne lit pas directement un second agrégat comptable et ne modifie ni le ledger ni les données opérationnelles.

```text
POSTED Accounting Ledger
        ↓
FinancialCalculationService
        ↓
Financial KPI Engine
        ↓
Management / FP&A / Closing
```

## Périmètre calculé

Les KPI de rentabilité suivants consomment les métriques traçables du moteur central :

| KPI | Formule | Source | Unité |
|---|---|---|---|
| Revenue | valeur `REVENUE` | lignes POSTED mappées | montant |
| Gross Profit | `REVENUE - COGS` | lignes POSTED mappées | montant |
| Gross Margin | `GROSS_PROFIT / REVENUE × 100` | métriques centrales | pourcentage |
| Operating Income | `REVENUE - COGS - OPERATING_EXPENSE` | lignes POSTED mappées | montant |
| Operating Margin | `OPERATING_INCOME / REVENUE × 100` | métriques centrales | pourcentage |
| Net Income | `REVENUE - COGS - OPERATING_EXPENSE + OTHER_INCOME - OTHER_EXPENSE` | lignes POSTED mappées | montant |
| Net Margin | `NET_INCOME / REVENUE × 100` | métriques centrales | pourcentage |

Tous les montants et ratios sont calculés avec `Decimal` et arrondis à deux décimales selon `ROUND_HALF_UP`. Une division par zéro retourne `value = null`, `status = NOT_READY` et une raison explicite.

## Traçabilité et statuts

Chaque métrique expose sa formule, sa période, ses dimensions, son module source et les identifiants des lignes POSTED utilisées. Une métrique ne peut pas être `READY` si aucune ligne source n’existe, même lorsqu’un mapping comptable est configuré.

| Statut | Signification |
|---|---|
| `READY` | les données sources nécessaires existent, sont équilibrées et sont traçables |
| `NOT_READY` | une configuration ou une source indispensable est absente |
| `INCOMPLETE` | le périmètre contient des données, mais un contrôle de cohérence ou de couverture empêche une conclusion complète |

Le statut global est `INCOMPLETE` lorsqu’une partie de la suite demandée reste indisponible. Le moteur ne transforme jamais une absence de données en zéro.

## Métriques opérationnelles et limites

`AR_OUTSTANDING` et `AP_OUTSTANDING` sont calculés à partir des factures réelles et des allocations canoniques datées. Les avoirs clients sont déduits uniquement lorsqu’un `CreditNote` réel existe dans le périmètre `as_of`. Les sorties exposent les montants bruts, payés, crédités, outstanding, overdue et les identifiants sources dans `inputs`.

`DSO` utilise exclusivement `average AR / credit revenue × days`, avec Revenue fourni par `FinancialCalculationService`. `DPO` utilise `average AP / validated supplier invoice total × days`. Les deux ratios retournent `NOT_READY` si le dénominateur ou la source obligatoire manque ou est nul.

`WORKING_CAPITAL` et `NET_WORKING_CAPITAL` utilisent `AR + Inventory - AP`. La valorisation Inventory est consommée depuis `StockBalance` uniquement pour un snapshot courant, car le modèle ne fournit pas encore d’historique de valorisation fiable. `LIQUIDITY` consomme directement `LiquidityControlService` et reste `INCOMPLETE` si le contrôle Treasury/Banking sous-jacent n’est pas READY. `CASH_COVERAGE` reste `NOT_READY` avec `CASH_COVERAGE_DEFINITION_NOT_CONFIGURED`, aucune formule silencieuse n’étant introduite.

La métrique `RECONCILIATION` consomme `AccountingTreasuryReconciliationService` et expose ses blockers, notamment les paiements non rapprochés, les écritures comptables absentes ou non POSTED, les différences de montant et les transactions bancaires orphelines.

## API

L’endpoint read-only est disponible sous `GET /api/v1/accounting/kpis`. Il accepte `fiscal_period_id` ou une paire `period_start` / `period_end`, ainsi que `dimension_id` et `dimension_value_id`. L’autorisation existante `kpi:read` est conservée.

Aucune migration, seed, configuration comptable, organisation ou donnée de démonstration n’est ajoutée par ce lot.
