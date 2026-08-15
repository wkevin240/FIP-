# Liasse SYSCOHADA de préparation et notes annexes

## Finalité

Ce lot produit une liasse SYSCOHADA de préparation à partir des données comptables déjà présentes pour une organisation. Il assemble la balance professionnelle, le bilan, le compte de résultat, le tableau de flux et des notes annexes structurées, sans créer d’organisation, de plan de comptes, d’écriture, d’exercice ou de mapping.

La route de lecture est `GET /api/v1/accounting/syscohada-liasse/` et l’export JSON est `GET /api/v1/accounting/syscohada-liasse/export.json`. Les deux exigent `professional_reporting:read`.

## Statut de préparation

| Statut | Signification | Contenu retourné |
|---|---|---|
| `NOT_READY` | Aucune écriture `POSTED` de l’organisation dans l’intervalle demandé | Aucun chiffre ; notes annexes vides ; raison explicite `NO_POSTED_ENTRIES_FOR_PERIOD` |
| `INCOMPLETE` | Des écritures existent mais une réconciliation, un mapping ou la configuration des flux est incomplète | Les états réellement calculés et les raisons explicites d’incomplétude |
| `READY` | Les contrôles de la balance, du bilan, des mappings et des flux sont réussis | Liasse et notes issues exclusivement des données réelles de l’organisation |

Les raisons d’incomplétude sont explicites, notamment `UNMAPPED_BALANCE_SHEET_ACCOUNTS`, `UNMAPPED_INCOME_STATEMENT_ACCOUNTS`, `CASH_FLOW_NOT_CONFIGURED`, `CASH_FLOW_CLASSIFICATION_INCOMPLETE` et `REPORTING_RECONCILIATION_FAILED`.

## Notes annexes

Les notes ne dupliquent pas de chiffres calculés manuellement. Chaque note référence le résultat réel de l’état source : bilan, compte de résultat ou tableau de flux. Lorsque les données ou la configuration manquent, sa charge utile est vide ou son statut est `NOT_READY` ; le logiciel ne complète jamais une note avec une valeur de démonstration.

## Export et Audit

L’export JSON conserve le statut réel de la liasse. Ainsi, une organisation sans donnée reçoit un fichier `NOT_READY` explicite et vide plutôt qu’un état fictif. Chaque export réussi écrit l’événement append-only `SYSCOHADA_LIASSE_EXPORTED` dans le journal Audit, avec l’organisation, la période et le statut exporté.

## Absence volontaire de migration et de seed

Ce lot est un agrégateur de lecture : il utilise les écritures, mappings professionnels et mappings de flux déjà persistés par les lots précédents. Il ne crée aucune nouvelle table et ne nécessite donc pas de migration Alembic. Aucun seed, script de démonstration ou donnée métier par défaut n’est introduit.
