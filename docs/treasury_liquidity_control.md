# Treasury Liquidity Control

## Existant réutilisé

FIP dispose déjà d’un ledger Accounting central, de TreasuryBankAccount, de BankTransaction, de l’import de relevés, du Banking Control Center, de CashForecastService, des factures AR/AP, de l’Audit et du RBAC. La branche de travail est empilée sur le HEAD de la PR #49 afin de réutiliser son BankingCrossReconciliationService sans fusionner ni dupliquer cette PR.

## Manque identifié

Les composants existants fournissent les mesures séparées, mais aucune vue opérationnelle ne les orchestre en un contrôle de liquidité unique. Il manquait la position cash actuelle, la liquidité nette, la projection, l’écart à un seuil explicitement configuré, les blockers propagés et des alertes explicables. Les paiements non affectés ne disposent pas d’une source canonique dans le modèle actuel ; le service retourne donc explicitement une source indisponible et `None`, sans inventer de montant.

## Périmètre construit

Le Liquidity Control est une read-model tenant-scopée. Il réutilise BankingCrossReconciliationService et CashForecastService, ne crée aucune écriture Accounting, ne propose aucune règle bancaire et ne génère aucune donnée de démonstration. Les alertes dépendant d’un seuil retournent `NOT_READY` lorsqu’aucune configuration d’organisation n’existe.

La configuration persistée est minimale, tenant-scopée et sans seuil financier par défaut. Elle est protégée par unicité organisation/code, contraintes PostgreSQL, RBAC et audit transactionnel.
