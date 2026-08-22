# Accounting ↔ Treasury ↔ Payments Reconciliation

Cette couche est une **orchestration en lecture seule**. Elle ne crée aucune écriture, ne modifie aucune transaction bancaire et ne change jamais le ledger Accounting.

L’endpoint `GET /api/v1/treasury/reconciliation/accounting-treasury?as_of=YYYY-MM-DD` exige la permission `treasury_reconciliation:read` et reste strictement limité à l’organisation du contexte courant.

Le contrôle rapproche les règlements clients et fournisseurs réellement présents avec les `BankTransaction` importées, en utilisant la date, la référence externe ou bancaire et le montant `Decimal(18, 2)`. Chaque règlement doit ensuite posséder un bridge de posting `POSTED` et pointer vers une `JournalEntry` elle-même `POSTED`. Les transactions bancaires peuvent aussi être couvertes par un rapprochement direct ou par des allocations partielles totalisant exactement leur montant absolu.

Le résultat est `NOT_READY` lorsque l’une des sources nécessaires est absente, `INCOMPLETE` lorsqu’un écart ou un blocage existe, et `READY` uniquement lorsque les relations sont complètes et cohérentes. Les blocages sont explicites : paiements non rapprochés, correspondances ambiguës, différences de montant, posting Accounting absent/non POSTED et transactions bancaires non résolues.

Aucune migration Alembic n’est nécessaire pour cet incrément : le service exploite exclusivement les tables et bridges existants. Aucun compte, mapping, règle ou jeu de données de démonstration n’est créé.
