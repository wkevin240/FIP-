# Cash Forecasting

Le Cash Forecasting projette les flux de trésorerie à partir de données opérationnelles présentes dans l’organisation. Le solde initial est constitué des soldes d’ouverture des comptes Treasury actifs et des mouvements bancaires importés antérieurs à la période.

Pour chaque date de la période :

> `mouvement net projeté = mouvement bancaire réel + encaissements AR attendus - décaissements AP attendus`

> `cash projeté de clôture = cash projeté de clôture précédent + mouvement net projeté`

Les encaissements AR sont issus des factures clients `ISSUED` ou `PARTIALLY_PAID` dont l’échéance réelle se trouve dans la période. Les décaissements AP utilisent les factures fournisseurs `VALIDATED` ou `PARTIALLY_PAID` et leur échéance réelle. Les montants payés et crédités sont déduits avec Decimal.

Le service est en lecture seule, tenant-scopé, sans écriture Accounting et sans règle de trésorerie inventée. Lorsqu’aucun compte bancaire actif ou aucune source opérationnelle réelle n’est disponible, le résultat retourne `NOT_READY` avec des blockers machine-readable. Aucun budget, taux, compte ou hypothèse fictive n’est créé.
