# Financial Variance Engine

Le Financial Variance Engine réutilise `FinancialCalculationService` et ne crée aucun moteur comptable ou financier parallèle. Les actuals proviennent exclusivement des lignes de journal liées à des écritures `POSTED`, tenant-scopées et filtrées sur la période demandée.

## Comparaisons

`PREVIOUS_PERIOD` compare la période demandée avec une période réelle de même durée immédiatement précédente. `PREVIOUS_YEAR` compare les mêmes bornes calendaires de l’exercice précédent. La variance est calculée par `actual - comparison`.

Le pourcentage de variance est `variance / ABS(comparison)` lorsque la comparaison est non nulle. Si la comparaison vaut zéro, la variance absolue peut rester disponible, mais `variance_percentage` est `null` avec une raison explicite.

## Sources indisponibles

Les comparaisons `BUDGET` et `FORECAST` retournent `NOT_READY` tant qu’une source approuvée et verrouillée n’est pas intégrée au contrat du moteur. Le service ne remplace jamais une source absente par zéro et n’invente aucune cause d’écart.

## Explicabilité

Chaque métrique expose sa valeur actuelle, sa valeur de comparaison, la variance, le pourcentage éventuel, les deux périodes, les comptes sources, les identifiants des lignes sources, les dimensions, le statut et la raison. Les périmètres déséquilibrés sont `INCOMPLETE` et ne produisent pas de variance présentée comme fiable.

## API

```text
GET /api/v1/accounting/financial-variance/variance
  ?period_start=YYYY-MM-DD
  &period_end=YYYY-MM-DD
  &comparison=PREVIOUS_PERIOD|PREVIOUS_YEAR|BUDGET|FORECAST
  [&dimension_id=...&dimension_value_id=...]
```

L’endpoint exige `professional_reporting:read`. Le calcul est read-only et ne produit aucun audit métier, car aucune mutation n’est effectuée ; la configuration de mappings reste auditée par le Financial Calculation Engine.
