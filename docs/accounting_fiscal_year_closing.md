# Clôture annuelle sécurisée

## Finalité

La clôture annuelle contrôle la préparation réelle d’un exercice avant de le faire passer de `OPEN` à `CLOSED`. Elle lit uniquement l’exercice, ses périodes et ses écritures existantes dans l’organisation active ; elle ne crée ni exercice, ni période, ni écriture, ni solde d’ouverture par défaut.

## Contrôles de préparation

| Bloqueur | Règle |
|---|---|
| `NO_FISCAL_PERIODS` | L’exercice ne contient aucune période réelle. |
| `OPEN_FISCAL_PERIODS` | Au moins une période de l’exercice est encore ouverte. |
| `LOCKED_FISCAL_PERIODS` | Au moins une période est verrouillée et nécessite une résolution explicite. |
| `DRAFT_JOURNAL_ENTRIES` | Des écritures brouillon restent présentes dans les périodes de l’exercice. |
| `FISCAL_YEAR_ALREADY_CLOSED` | L’exercice a déjà été clôturé. |

L’aperçu ne modifie rien. La clôture n’est possible que si aucun bloqueur n’est présent ; elle verrouille l’exercice avec une transaction, passe le statut à `CLOSED` et écrit l’événement append-only `FISCAL_YEAR_CLOSED` dans Audit.

## API

| Route | Permission | Action |
|---|---|---|
| `GET /api/v1/accounting/fiscal-years/{id}/closing-preview` | `fiscal_year:read` | Retourne les contrôles et bloqueurs réels. |
| `POST /api/v1/accounting/fiscal-years/{id}/close` | `fiscal_year:update` | Clôture l’exercice si l’aperçu est prêt. |

Le report automatique des soldes vers un nouvel exercice reste volontairement hors de ce lot : il doit être exécuté à partir d’un exercice suivant créé et configuré par l’utilisateur, jamais par une donnée fictive générée par le logiciel.
