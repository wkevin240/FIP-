# Banking Control Center — réconciliation croisée

Le rapport `GET /treasury/banking-control/cross-reconciliation` fournit une vue en lecture seule, tenant-scopée et datée de la cohérence opérationnelle entre les transactions bancaires importées, les états du Banking Control Center, les créances clients ouvertes et les dettes fournisseurs ouvertes.

Les montants bancaires sont séparés en entrées et sorties puis réconciliés par `net_bank_movement = bank_inflows - bank_outflows`. Les créances AR et dettes AP sont calculées à partir des factures réelles de l’organisation, en `Decimal`, après prise en compte des règlements et avoirs existants.

Le rapport retourne `READY` uniquement si des transactions bancaires existent et qu’elles sont toutes `RECONCILED`. Sinon, il retourne `INCOMPLETE` avec des blockers explicites comme `NO_BANK_TRANSACTIONS`, `UNRESOLVED_BANK_TRANSACTIONS`, `NO_OPEN_AR_SOURCE` ou `NO_OPEN_AP_SOURCE`. Il ne crée aucune proposition, aucune écriture, aucune règle bancaire et aucune donnée de démonstration.
