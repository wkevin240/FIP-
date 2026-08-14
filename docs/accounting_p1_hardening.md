# Durcissement Accounting P1

## Décisions d’architecture

Le lot P1 conserve l’architecture `API → Service → Repository → PostgreSQL`. Les écritures restent créées au statut `DRAFT`; seule la procédure PostgreSQL privilégiée `post_journal_entry()` peut les faire passer à `POSTED`. Une écriture comptabilisée ne peut devenir `VOIDED` qu’après comptabilisation d’une écriture inverse tenant-scopée et par la procédure `void_journal_entry()`.

> Une correction ne réécrit jamais l’historique : elle est composée d’une contre-passation de l’écriture originale et d’une nouvelle écriture corrective, avec les événements Audit dans la transaction métier commune.

## Invariants

| Invariant | Niveau de garantie |
|---|---|
| Équilibre débit/crédit et période ouverte à la comptabilisation | Service, règles de domaine et déclencheur PostgreSQL |
| `DRAFT → POSTED` | Procédure PostgreSQL protégée par privilèges et secret de comptabilisation |
| `POSTED → VOIDED` | Procédure PostgreSQL ; une contre-passation `POSTED` doit exister |
| Une seule contre-passation | Clé unique `(organization_id, reversal_of_id)` |
| Liens originaux et contre-passations inter-tenant | Clé étrangère composite `(organization_id, reversal_of_id)` |
| Historique `POSTED` / `VOIDED` | Privilèges P0 et déclencheurs PostgreSQL |
| Balance, grand livre et comparatifs | Requêtes tenant-scopées sur les seules écritures `POSTED`, montants `Decimal` |

## États P1

La balance générale agrège débit, crédit et solde par compte. Le grand livre utilise un ordre stable : date d’écriture, numéro d’écriture, numéro de ligne. Les comparatifs distinguent période courante, période précédente et cumul au terme courant. Les écritures `VOIDED` ne contribuent pas aux états ; leur effet économique est annulé par la contre-passation `POSTED` correspondante.
