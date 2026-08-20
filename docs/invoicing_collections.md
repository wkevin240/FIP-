# Recouvrement client

Le snapshot de recouvrement présente les encours des factures clients `ISSUED` et `PARTIALLY_PAID` à partir des données réelles de l’organisation. Il calcule les montants en `Decimal`, déduit les règlements et avoirs déjà enregistrés, classe les factures par échéance et expose les priorités `NORMAL`, `HIGH`, `CRITICAL` ou `REVIEW`.

Le service est strictement en lecture seule. Il ne crée aucune relance, ne modifie aucune facture, ne comptabilise aucune écriture et n’invente ni client, ni compte, ni échéance. En l’absence d’encours réel, l’API retourne `NOT_READY` avec le blocker `NO_OPEN_RECEIVABLES`.
