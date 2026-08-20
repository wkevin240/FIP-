# Règles de reconnaissance bancaire et propositions Accounting

## Objet

Le module de règles bancaires transforme une transaction issue d’un relevé normalisé en une **proposition comptable contrôlée**. Il complète les imports CSV, OFX v2 XML et MT940 : tous alimentent le modèle canonique `BankTransaction`, qui est ensuite évalué par les mêmes règles tenant-scopées.

> Une règle ne crée jamais une écriture comptable. Seule la validation explicite d’une proposition crée et comptabilise l’écriture équilibrée correspondante.

Le module n’ajoute ni compte comptable, ni journal, ni règle par défaut. Chaque organisation doit configurer ses propres comptes actifs, son profil de comptabilisation Trésorerie et ses propres règles avant toute validation.

## Flux contrôlé

| Étape | Entrée | Effet | Garantie |
|---|---|---|---|
| Import | CSV, OFX v2 XML ou MT940 | Création/dédoublonnage de `BankTransaction` | Idempotence, isolation tenant, `Decimal`, Audit et transaction atomique. |
| Paramétrage | Règle explicite de l’organisation | Configuration d’un critère et d’un compte de contrepartie réel | Aucune règle sans critère ; compte actif de la même organisation obligatoire. |
| Évaluation | Transaction bancaire | Proposition `PENDING`, absence de proposition ou ambiguïté | Aucune écriture Accounting n’est créée à cette étape. |
| Décision | Validation ou rejet explicite avec clé d’idempotence | `VALIDATED` avec écriture ou `REJECTED` sans écriture | Verrous PostgreSQL, Audit et transition atomique. |
| Rapprochement | Écriture comptabilisée, si nécessaire | Processus de rapprochement bancaire existant et distinct | Le module ne rapproche pas automatiquement une transaction. |

Le rapprochement de transaction bancaire et la comptabilisation répondent à deux questions différentes. La présente fonctionnalité propose le compte de contrepartie à utiliser pour l’écriture issue du relevé. Le rapprochement est exécuté par les parcours dédiés lorsque l’organisation dispose d’une écriture source à rapprocher.

## Règles de reconnaissance

Une règle `BankAccountingRule` appartient à une seule organisation. Elle comprend un nom unique, un compte de contrepartie, une priorité numérique, une catégorie facultative et un statut actif. Les critères disponibles sont les suivants :

| Critère | Comportement |
|---|---|
| `description_pattern` | Expression régulière insensible à la casse appliquée à la description bancaire. |
| `reference_pattern` | Expression régulière insensible à la casse appliquée à la référence bancaire. |
| `amount_min` / `amount_max` | Bornes inclusives appliquées à la valeur absolue du montant en `Decimal(18,2)`. |
| `direction` | `CREDIT` pour un montant strictement positif ou `DEBIT` pour un montant strictement négatif. |

Les critères renseignés sont combinés par **ET**. Au moins un critère est obligatoire. La priorité la plus faible est la plus importante. Lorsque plusieurs règles correspondent avec la même meilleure priorité, FIP retourne `AMBIGUOUS` et ne choisit aucune règle. Lorsqu’aucune règle ne correspond, FIP retourne `NO_MATCH`. Ces deux résultats sont volontairement non comptabilisants.

La catégorie est une information de classement fournie par l’organisation. Elle n’altère pas les montants, les sens débit/crédit ou le rapprochement.

## Propositions et décisions

Une proposition capture un instantané immuable des éléments pertinents de la règle et de la transaction. Cet instantané est haché en SHA-256 afin d’assurer l’idempotence de la génération. Le changement ultérieur d’une règle ne modifie donc jamais une proposition existante.

| Statut | Écriture Accounting | Décision possible |
|---|---|---|
| `PENDING` | Aucune | Validation ou rejet explicite. |
| `VALIDATED` | Une écriture `POSTED` liée à la transaction | Aucune nouvelle validation ni rejet. |
| `REJECTED` | Aucune | Aucune nouvelle validation ni rejet. |

La validation exige une clé `idempotency_key` propre à l’organisation. La répétition exacte de la même validation renvoie la proposition déjà validée ; la réutilisation d’une clé sur une autre proposition est refusée. La validation appelle exclusivement `TreasuryAccountingService`, qui délègue à `JournalEntryService` pour créer une écriture équilibrée dans une période fiscale ouverte. Pour une entrée positive, le compte bancaire est débité et le compte de contrepartie est crédité ; pour une sortie, les sens sont inversés. Les montants restent en `Decimal`.

Le rejet exige également une clé d’idempotence et un motif non vide. Il ne produit aucune écriture.

## Endpoints

Tous les endpoints ci-dessous sont préfixés par `/api/v1/treasury/transactions` et s’exécutent dans l’organisation portée par le jeton authentifié.

| Endpoint | Permission | Usage |
|---|---|---|
| `GET /accounting-rules` | `bank_rule:read` | Liste ordonnée des règles de l’organisation. |
| `POST /accounting-rules` | `bank_rule:create` | Crée une règle explicite après validation du compte et des critères. |
| `PUT /accounting-rules/{rule_id}` | `bank_rule:update` | Met à jour une règle existante, sans modifier les instantanés de propositions historiques. |
| `POST /{transaction_id}/accounting-proposals` | `bank_transaction:propose` | Évalue une transaction et génère au plus une proposition `PENDING`. |
| `GET /accounting-proposals/{proposal_id}` | `bank_rule:read` | Consulte une proposition appartenant à l’organisation active. |
| `POST /accounting-proposals/{proposal_id}/validate` | `bank_transaction:validate_accounting` | Valide explicitement et comptabilise la proposition. |
| `POST /accounting-proposals/{proposal_id}/reject` | `bank_transaction:validate_accounting` | Rejette explicitement la proposition avec un motif. |

Les requêtes de validation et de rejet portent un corps JSON comprenant `idempotency_key`. Un rejet ajoute `rejection_reason`.

## Intégrité, sécurité et concurrence

La migration `0022_bank_rules_accounting` crée `bank_accounting_rules` et `bank_transaction_accounting_proposals`. Les références à un compte, une transaction, une règle et une écriture utilisent des clés étrangères composites incluant `organization_id`. Une référence inter-organisation est donc refusée directement par PostgreSQL.

Les tables sont détenues par `fip_accounting_owner`. Le rôle applicatif `fip_user` reçoit uniquement les droits nécessaires : lecture/insertion/mise à jour des règles et lecture/insertion, puis mise à jour limitée aux colonnes de décision des propositions. Il ne reçoit aucun droit de suppression sur ces tables.

Le service sérialise les opérations concurrentes avec `pg_advisory_xact_lock` sur la configuration organisationnelle, la transaction bancaire et la proposition concernée. La base impose aussi l’unicité de l’instantané de proposition par transaction, l’unicité d’une clé de décision par organisation et l’unicité de l’écriture liée. Les décisions incohérentes, notamment une proposition `VALIDATED` sans écriture liée ou une proposition `PENDING` déjà dotée d’une décision, sont rejetées par une contrainte `CHECK` PostgreSQL.

Chaque création/modification de règle, génération, validation et rejet écrit un événement Audit dans la même transaction. Une erreur lors de la comptabilisation, notamment une période fermée ou un profil Trésorerie absent, annule la décision et l’événement Audit associé.

## Couverture de tests

La suite couvre les résultats `PROPOSED`, `EXISTING_PROPOSAL`, `NO_MATCH` et `AMBIGUOUS`, les règles de priorité, les montants `Decimal`, la validation équilibrée, le rejet, la période fermée, l’isolation entre organisations et les événements Audit. Les tests PostgreSQL réels vérifient en plus les clés étrangères composites, le refus d’une transition d’état directe incohérente et les générations/validations concurrentes qui ne doivent produire qu’une proposition, une écriture et une trace Audit.
