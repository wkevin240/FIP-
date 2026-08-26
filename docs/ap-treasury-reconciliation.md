# Preview AP → Treasury

Cette fonctionnalité propose des règlements fournisseurs candidats pour une transaction bancaire importée. Elle réutilise la transaction bancaire canonique, les allocations fournisseurs canoniques et les écritures Accounting déjà postées ; elle ne crée aucune règle comptable, aucune écriture, aucune allocation et aucun rapprochement.

La recherche est strictement tenant-scopée et ne considère que les `SupplierPayment` possédant un posting fournisseur `POSTED` ainsi qu’une écriture Accounting `POSTED`. Une transaction bancaire entrante est exclue : le preview AP ne traite que les sorties bancaires, représentées par un montant négatif selon la convention Treasury.

Les montants sont calculés exclusivement en `Decimal` à deux décimales. Le montant alloué est la somme réelle des `SupplierPaymentAllocation` de l’organisation. Une absence d’allocation est représentée par `allocated_amount = null`, et non par un zéro silencieux. Une allocation partielle expose `unapplied_amount` et reste incomplète. L’écart compare la transaction bancaire au montant réellement alloué lorsqu’une relation canonique existe.

Les états du preview sont les suivants :

| État | Signification |
|---|---|
| `READY` | Une proposition possède une allocation canonique complète et un montant alloué égal à la sortie bancaire. |
| `INCOMPLETE` | Une proposition existe, mais ses allocations sont absentes, partielles ou présentent un écart. |
| `NOT_READY` | Aucun candidat exploitable n’est trouvé ou la transaction n’est pas une sortie bancaire. |
| `ALREADY_RECONCILED` | La transaction bancaire est déjà rapprochée. |

Chaque candidat conserve un état `READY` ou `INCOMPLETE` et expose les raisons de matching, le nombre d’allocations, le montant alloué, le montant non appliqué et l’écart. La validation manuelle doit utiliser les mécanismes Treasury de rapprochement existants dans un incrément séparé ; aucun endpoint de preview ne modifie `BankTransaction`, `SupplierPayment`, `PurchaseInvoice`, `SupplierPaymentAllocation`, `BankReconciliation` ou le ledger.
