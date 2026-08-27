# Financial Calculation Engine — Rentabilité

Ce premier incrément introduit un moteur de calcul financier réutilisable au-dessus du ledger Accounting. Il ne crée aucun ledger parallèle et ne comptabilise aucune opération.

## Sources et périmètre

Le moteur lit uniquement les `JournalEntryLine` rattachées à des `JournalEntry` `POSTED`, dans l’organisation courante et dans l’intervalle `[period_start, period_end]`. Les classifications ne sont pas déduites des numéros de comptes : elles doivent être configurées explicitement par l’organisation dans `profitability_account_mappings`.

Les catégories disponibles sont `REVENUE`, `COGS`, `OPERATING_EXPENSE`, `OTHER_INCOME` et `OTHER_EXPENSE`. Aucun compte ni mapping n’est inséré par migration.

## Formules

| Métrique | Formule |
|---|---|
| Revenue | crédit − débit des comptes `REVENUE` |
| COGS | débit − crédit des comptes `COGS` |
| Operating Expenses | débit − crédit des comptes `OPERATING_EXPENSE` |
| Other Income | crédit − débit des comptes `OTHER_INCOME` |
| Other Expense | débit − crédit des comptes `OTHER_EXPENSE` |
| Gross Profit | Revenue − COGS |
| Operating Income | Revenue − COGS − Operating Expenses |
| Net Income | Revenue − COGS − Operating Expenses + Other Income − Other Expense |

Chaque métrique retourne sa valeur `Decimal`, sa formule, sa période, les comptes utilisés, les lignes POSTED utilisées et son état `READY` ou `NOT_READY` avec une raison explicite. Le moteur vérifie également l’équilibre débit/crédit du périmètre ledger sélectionné.

## API

`POST /api/v1/accounting/financial-calculation/profitability-mappings` configure une classification avec la permission `professional_reporting:configure`.

`GET /api/v1/accounting/financial-calculation/profitability-mappings` liste les mappings actifs avec `professional_reporting:read`.

`GET /api/v1/accounting/financial-calculation/profitability?period_start=YYYY-MM-DD&period_end=YYYY-MM-DD` calcule la rentabilité avec `professional_reporting:read`.

Lorsque Revenue, COGS ou Operating Expenses ne sont pas explicitement configurés, les métriques dérivées et le résultat global restent `NOT_READY`. Le moteur ne fabrique jamais de chiffres explicatifs.
