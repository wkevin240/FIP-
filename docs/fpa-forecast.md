# FP&A Forecast

Le Forecast Engine calcule une vue de prévision à la demande à partir de trois sources existantes : les écritures `POSTED` du ledger, les lignes d’un budget `APPROVED` ou `LOCKED`, et les hypothèses d’un scénario `APPROVED` ou `LOCKED` du même exercice et de la même organisation.

Pour chaque ligne de budget, la formule est déterministe et entièrement en `Decimal(18,2)` : `forecast_amount = actual_amount + approved_budget_amount + scenario_assumption_amount`. Les actuals sont calculés exclusivement par agrégation des mouvements `debit - credit` des écritures `POSTED`; les écritures `DRAFT` ou `VOIDED` sont exclues. Les hypothèses sont rapprochées par période, compte et valeur analytique.

Le calcul ne crée ni écriture, ni compte, ni scénario, ni donnée dérivée persistante. Si le budget ou le scénario n’est pas approuvé, l’API retourne `NOT_READY`; si aucun budget n’existe, elle retourne `INCOMPLETE`. Une absence de données réelles ne donne jamais lieu à des chiffres inventés.

Endpoint : `GET /accounting/forecasts?budget_id=<id>&scenario_id=<id>`. L’accès est en lecture seule via `forecast:read` et reste tenant-scopé.
