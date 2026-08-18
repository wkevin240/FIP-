# Banking Control Center

Le Banking Control Center supervise les transactions issues des relevés bancaires sans créer de moteur bancaire ou comptable parallèle. Il réutilise le modèle canonique `BankTransaction`, les imports CSV/OFX/MT940, les règles de reconnaissance, les propositions comptables et les rapprochements existants.

## États contrôlés

| État | Signification | Clôture du relevé |
|---|---|---|
| `NO_MATCH` | Aucune règle active ne correspond | Bloquée |
| `AMBIGUOUS` | Plusieurs règles ont la meilleure priorité | Bloquée |
| `PENDING` | Une proposition attend une décision explicite | Bloquée |
| `REJECTED` | Une proposition a été rejetée | Bloquée |
| `INVALID_RULE` | La configuration de la règle est invalide | Bloquée |
| `POSTED_UNRECONCILED` | L’écriture existe, mais le rapprochement bancaire reste à faire | Bloquée |
| `RECONCILED` | La transaction est rapprochée avec une écriture POSTED | Autorisée |

Le rafraîchissement est supervisé par l’utilisateur et peut générer une proposition `PENDING` uniquement lorsqu’une règle existante correspond. Il ne valide jamais une proposition et ne comptabilise jamais automatiquement une transaction.

## API

| Méthode | Endpoint | Permission |
|---|---|---|
| `POST` | `/api/v1/treasury/banking-control/imports/{statement_import_id}/refresh` | `bank_control:refresh` |
| `GET` | `/api/v1/treasury/banking-control/exceptions` | `bank_control:read` |
| `POST` | `/api/v1/treasury/banking-control/imports/{statement_import_id}/close` | `bank_control:close` |

La clôture est atomique et refuse tout relevé comportant une transaction non rapprochée. Elle crée un enregistrement audité avec les compteurs importés, rapprochés et non résolus. Les exceptions et clôtures sont tenant-scopées par clés étrangères composites PostgreSQL.

La migration `0024_banking_control` dépend de `0023_procurement_invoices`. Elle ne crée aucune donnée de démonstration et attribue les nouvelles tables à `fip_accounting_owner` avec des ACL minimales pour `fip_user`.
