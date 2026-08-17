# Règles de rapprochement bancaire

Le rapprochement bancaire associe les mouvements provenant des relevés aux écritures comptables **POSTED** qui portent un mouvement sur le compte bancaire concerné. Les montants sont exclusivement traités en `Decimal(18, 2)` ; aucune conversion en `float` n’est autorisée.

| Mode | Portée | Règle de montant | Usage |
|---|---|---|---|
| Exact manuel | Une transaction ↔ une écriture | Les montants signés doivent être identiques | Rapprochement historique conservé pour les cas simples |
| Exact automatique | Une transaction ↔ une écriture non ambiguë | Même montant, même sens et fenêtre de date contrôlée | L’automatisation ne traite que les associations déterministes |
| Partiel/groupé manuel | Plusieurs transactions ↔ plusieurs écritures du même compte bancaire | Chaque allocation positive est plafonnée par le reste disponible des deux côtés | Encaissements regroupés, règlements fractionnés et frais bancaires ventilés |

## Invariants des allocations partielles et groupées

Un lot de rapprochement regroupe une ou plusieurs allocations pour un **seul compte bancaire actif**, dans une seule organisation. Chaque allocation référence une transaction bancaire et une écriture comptable par des clés étrangères composites incluant `organization_id`.

> Une allocation ne peut jamais dépasser le montant restant de la transaction bancaire, ni le mouvement bancaire restant de l’écriture comptable. Les deux mouvements doivent avoir le même sens comptable.

Le reste d’une transaction est la valeur absolue de son montant moins la somme de ses allocations validées. Le reste d’une écriture est calculé séparément pour le compte bancaire du lot ; il est égal au mouvement net de ce compte dans l’écriture, moins les allocations déjà validées pour ce même compte. Une transaction n’est marquée comme rapprochée que lorsque son reste est exactement nul.

Les écritures et transactions déjà rapprochées par le mécanisme exact ne peuvent pas être réutilisées dans le mécanisme partiel/groupé. Inversement, une transaction ou une écriture qui porte déjà une allocation partielle ne peut plus être rapprochée par l’endpoint exact. Cette séparation préserve l’interprétation historique des rapprochements existants.

## Atomicité, concurrence et idempotence

La requête `POST /api/v1/accounting/bank-reconciliation/allocations` exige une clé HTTP `Idempotency-Key`. Celle-ci est unique par organisation. Une répétition de la même clé retourne le lot existant et ne crée ni allocation ni événement d’Audit supplémentaire.

Avant lecture des montants disponibles, le service obtient des verrous transactionnels PostgreSQL déterministes sur la clé d’idempotence, les transactions et les écritures concernées. Deux requêtes concurrentes sur la même ressource sont donc sérialisées. Une requête concurrente identique renvoie le même lot ; une requête différente qui excède le reste disponible est refusée avec une erreur métier `422` sans effet partiel.

La création du lot, des allocations, la mise à jour de l’état de rapprochement complet des transactions et l’événement `BANK_RECONCILIATION_BATCH_APPLIED` sont exécutés dans la même transaction. Tout rejet provoque un rollback intégral.

## Sécurité et accès

Les tables `bank_reconciliation_batches` et `bank_reconciliation_allocations` sont détenues par `fip_accounting_owner`. Le rôle applicatif `fip_user` possède uniquement les droits `SELECT` et `INSERT` nécessaires. Les FK composites interdisent au niveau PostgreSQL les références croisées entre organisations. L’API applique la permission `bank_reconciliation:match` pour les allocations et conserve les permissions existantes pour les opérations exactes.

## Limites assumées

L’automatisation reste intentionnellement limitée au rapprochement exact non ambigu. Les allocations partielles et groupées sont une opération manuelle contrôlée, car leur détermination automatique nécessite des règles de rapprochement explicables et une validation métier additionnelle.
