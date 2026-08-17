# Intégration Inventaire → Accounting

Les réceptions, sorties et ajustements de stock effectués via les routes métier sont comptabilisés dans leur transaction de mouvement lorsque l’organisation a configuré un profil comptable actif. Le profil configure un journal, un compte de stock `ASSET`, une contrepartie de réception `LIABILITY`, un coût des ventes `EXPENSE`, un gain d’ajustement `REVENUE` et une perte d’ajustement `EXPENSE`.

Les montants proviennent exclusivement de `StockMovement.total_value`, calculé par les règles de coût moyen pondéré du module Inventaire et conservé en `Decimal`. Une réception débite le stock et crédite la contrepartie ; une sortie débite le coût des ventes et crédite le stock ; les ajustements utilisent les comptes de gain ou de perte correspondants. Les transferts entre entrepôts sont explicitement exclus : ils ne changent pas la valeur de stock au niveau de l’organisation.

Le moteur utilise `JournalEntryService`, bloque les périodes non ouvertes, exige un profil réel et crée une liaison source unique vers l’écriture `POSTED`. La migration `0017_inventory_accounting` impose l’isolation `organization_id` par clés étrangères composites et la source unique au niveau PostgreSQL. Aucun compte, journal, entrepôt, produit ou mouvement de démonstration n’est créé.
