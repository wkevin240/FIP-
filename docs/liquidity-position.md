# Position de liquidité

La position de liquidité agrège uniquement les données réelles de l’organisation. Pour chaque compte bancaire Treasury actif, le solde de clôture est calculé ainsi :

> `solde de clôture = solde d’ouverture + mouvements bancaires signés jusqu’à la date de reporting`

Les encaissements sont les mouvements bancaires positifs et les décaissements la valeur absolue des mouvements négatifs. Le service expose également les créances clients et dettes fournisseurs présentes dans les factures opérationnelles, puis calcule :

> `liquidité nette = cash disponible + créances à recevoir - dettes fournisseurs`

Aucun solde bancaire n’est inventé lorsqu’aucun compte Treasury actif n’existe. Le cash forecast retourne `NOT_READY` tant qu’un mapping organisationnel réel entre prévisions FP&A et mouvements de trésorerie n’est pas configuré. Cette limite est volontaire : une prévision comptable générique ne doit pas être présentée comme une prévision de cash.

La route est en lecture seule, tenant-scopée, utilise exclusivement Decimal et exige `period_start` et `as_of_date`. Aucun mouvement bancaire, paiement, facture ou écritures Accounting n’est modifié.
