# Preview AP → Treasury

Cette fonctionnalité propose des règlements fournisseurs candidats pour une transaction bancaire importée. Elle réutilise la transaction bancaire canonique et les écritures Accounting déjà postées ; elle ne crée aucune règle comptable, aucune écriture et aucun rapprochement.

La recherche est strictement tenant-scopée et ne considère que les `SupplierPayment` possédant une écriture de posting `POSTED`. Les critères sont le montant absolu, la date dans une fenêtre explicite et la référence externe lorsqu’elle est disponible. Les résultats exposent les raisons de matching, l’écart de montant et l’écart de date.

Les états sont `NO_MATCH`, `CANDIDATES_FOUND` et `ALREADY_RECONCILED`. Chaque candidat reste `PROPOSED`. La validation manuelle doit utiliser les mécanismes Treasury de rapprochement existants dans un incrément séparé ; aucun endpoint de preview ne modifie `BankTransaction`, `BankReconciliation` ou le ledger.
