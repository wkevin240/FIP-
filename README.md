# FIP — Financial, Inventory and Payroll System

FIP est le socle backend d’un système financier modulaire destiné aux flux de comptabilité, inventaire, paie, trésorerie, facturation et audit dans un contexte OHADA. Le projet est développé en Python avec FastAPI, SQLAlchemy asynchrone et PostgreSQL.

> **État actuel.** Cette révision constitue un socle de développement. Les fonctionnalités exposées couvrent le référentiel comptable, les exercices et périodes fiscales, les journaux, les écritures équilibrées, la clôture contrôlée des périodes, le reporting financier de base, le rapprochement bancaire, la gestion TVA, le premier vertical Inventaire et le premier vertical Facturation. Les autres domaines présents dans l’arborescence sont en cours d’implémentation et ne doivent pas être considérés comme livrés.

## Architecture

Le code suit une séparation par responsabilités afin de préserver les règles métier et l’isolement entre organisations :

| Répertoire | Responsabilité |
|---|---|
| `backend/app/api` | Routes FastAPI, dépendances d’authentification et permissions. |
| `backend/app/services` | Cas d’usage et orchestration transactionnelle. |
| `backend/app/repositories` | Accès asynchrone aux données. |
| `backend/app/models` | Modèles SQLAlchemy. |
| `backend/app/domain` | Règles métier indépendantes du transport HTTP. |
| `backend/app/schemas` | Contrats de validation et de sérialisation Pydantic. |
| `backend/tests` | Tests unitaires et, à terme, tests d’intégration. |

Les routes métier sont isolées par `organization_id` et protégées par une politique de permissions RBAC.

## Prérequis

Le projet cible **Python 3.11 ou supérieur** et utilise [Poetry](https://python-poetry.org/) pour la gestion des dépendances. Une base PostgreSQL est nécessaire pour exécuter l’API avec ses données applicatives.

## Installation

Clonez le dépôt puis installez les dépendances, y compris les outils de développement :

```bash
git clone https://github.com/wkevin240/FIP-.git
cd FIP-
poetry sync --no-interaction
```

Créez ensuite un fichier `.env` à partir de l’exemple fourni et renseignez au minimum les paramètres PostgreSQL et une clé JWT forte :

```bash
cp .env.example .env
```

> Ne versionnez jamais le fichier `.env`. En production, injectez les secrets depuis le gestionnaire de secrets de votre environnement.

## Lancer l’API

Après avoir configuré l’environnement, démarrez le serveur de développement depuis la racine du dépôt :

```bash
poetry run uvicorn app.main:app --app-dir backend --reload
```

L’API expose alors les ressources suivantes :

| Ressource | Chemin |
|---|---|
| Vérification de santé | `GET /health` |
| Spécification OpenAPI | `GET /api/v1/openapi.json` |
| Comptes comptables | `/api/v1/accounting/accounts` |
| Exercices fiscaux | `/api/v1/accounting/fiscal-years` |
| Périodes fiscales | `/api/v1/accounting/fiscal-periods` |
| Journaux comptables | `/api/v1/accounting/journals` |
| Écritures comptables | `/api/v1/accounting/journal-entries` |
| Prévisualisation et clôture de période | `/api/v1/accounting/period-closings` |
| Bilan et compte de résultat | `/api/v1/accounting/reports` |
| Rapprochement bancaire | `/api/v1/accounting/bank-reconciliation` |
| Gestion TVA | `/api/v1/accounting/vat` |
| Produits Inventaire | `/api/v1/inventory/products` |
| Entrepôts Inventaire | `/api/v1/inventory/warehouses` |
| Mouvements et soldes de stock | `/api/v1/inventory/stock` |
| Factures commerciales | `/api/v1/invoicing/invoices` |
| Avoirs commerciaux | `/api/v1/invoicing/credit-notes` |
| Règlements de facture | `/api/v1/invoicing/payments` |

Les routes métier requièrent une authentification et les permissions associées au rôle de l’organisation active.

## Journaux et écritures équilibrées

Un journal est créé au sein d’une organisation, avec un code unique. Une écriture doit être rattachée à un journal actif et à une période fiscale ouverte. Elle comporte au minimum deux lignes ; chaque ligne est exclusivement au débit ou au crédit, et le total des débits doit être exactement égal au total des crédits.

L’écriture est d’abord créée au statut `DRAFT`. L’opération `POST /api/v1/accounting/journal-entries/{journal_entry_id}/post` effectue une seconde vérification des comptes, de la période et de l’équilibre, puis la passe au statut `POSTED`. Une écriture déjà comptabilisée ne peut pas être comptabilisée une seconde fois.

## Clôture de période

Avant toute clôture, `GET /api/v1/accounting/period-closings/periods/{fiscal_period_id}/preview` calcule le nombre d’écritures et de lignes comptabilisées, les totaux débit/crédit et une empreinte SHA-256 déterministe. La clôture via `POST /api/v1/accounting/period-closings/periods/{fiscal_period_id}` est réservée à la permission `fiscal_period:close`.

La fermeture s’exécute dans une transaction avec verrouillage de la période. Elle refuse les périodes non ouvertes, tout brouillon résiduel et toute écriture comptabilisée individuellement déséquilibrée. À succès, elle passe la période à `CLOSED`, enregistre les agrégats et l’empreinte de contrôle dans un registre unique, puis empêche l’ajout ou la comptabilisation concurrente d’écritures.

## Reporting financier

Le bilan est disponible via `GET /api/v1/accounting/reports/balance-sheet?as_of_date=YYYY-MM-DD`. Il agrège uniquement les lignes d’écritures `POSTED` jusqu’à la date demandée. Les actifs sont présentés selon `débit − crédit`, tandis que les passifs et capitaux propres suivent `crédit − débit`. Le résultat courant, calculé comme produits moins charges, est inclus dans les capitaux propres ; le rapport est refusé si l’égalité **Actif = Passif + Capitaux propres** n’est pas respectée.

Le compte de résultat est disponible via `GET /api/v1/accounting/reports/income-statement?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`. Il limite strictement les mouvements à l’intervalle inclusif fourni et calcule le résultat net comme **Produits − Charges**. Les deux routes exigent la permission `financial_report:read`.

## Rapprochement bancaire

Les lignes de relevé bancaires sont enregistrées par `POST /api/v1/accounting/bank-reconciliation/transactions`, avec un identifiant externe unique par organisation et compte bancaire. Les suggestions de correspondance proviennent de `GET /api/v1/accounting/bank-reconciliation/transactions/{transaction_id}/candidates` : elles ne retiennent que les écritures `POSTED` non déjà rapprochées, dans la fenêtre de date demandée, dont le mouvement sur le compte bancaire a le même sens et le même montant.

La validation par `POST /api/v1/accounting/bank-reconciliation/transactions/{transaction_id}/match` verrouille la ligne bancaire et l’écriture concernée. Elle refuse tout écart de montant, toute différence de sens, toute écriture non comptabilisée et tout double rapprochement. Le registre conserve l’auteur, l’horodatage, le montant absolu validé et la méthode employée. Les permissions `bank_reconciliation:create`, `bank_reconciliation:read` et `bank_reconciliation:match` séparent l’import, la lecture et la validation.

## Gestion TVA

Le référentiel de taux TVA est géré sous `/api/v1/accounting/vat/rates`. Chaque taux est propre à une organisation, daté par `effective_from` et éventuellement `effective_to`, et possède un code unique pour sa date d’effet. Les taux sont bornés entre **0,00 %** et **100,00 %**. Les comptes de TVA déductible et collectée, lorsqu’ils sont configurés, doivent être respectivement des comptes actifs de type `ASSET` et `LIABILITY` appartenant à la même organisation.

Les opérations de calcul et d’enregistrement emploient exclusivement `Decimal`. Le montant de TVA est calculé avec la formule `montant taxable × taux / 100`, puis arrondi au centime selon la règle `ROUND_HALF_UP`. Une écriture TVA (`POST /api/v1/accounting/vat/entries`) ne peut être rattachée qu’à une écriture comptable `POSTED`, à la même date, et une écriture comptable ne peut porter qu’un seul enregistrement TVA. Le taux doit être actif à la date fiscale ; les écritures d’achat utilisent la direction `INPUT`, tandis que les écritures de vente utilisent `OUTPUT`.

La synthèse déclarative est disponible via `GET /api/v1/accounting/vat/declaration?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`. Elle agrège les montants de TVA collectée et déductible sur l’intervalle inclusif et calcule le solde comme **TVA collectée − TVA déductible**. Les permissions `vat:create`, `vat:read` et `vat:update` séparent respectivement l’enregistrement, la consultation et l’administration des taux.

## Gestion Inventaire

Le module Inventaire expose deux référentiels tenant-scopés : les produits sous `/api/v1/inventory/products` et les entrepôts sous `/api/v1/inventory/warehouses`. Les SKU Produit et les codes Entrepôt sont uniques dans leur organisation. Un produit ou entrepôt désactivé reste consultable pour préserver l’historique, mais ne peut plus être utilisé pour une nouvelle opération de stock.

Les opérations de stock sont disponibles sous `/api/v1/inventory/stock` : réceptions (`POST /receipts`), sorties (`POST /issues`), ajustements (`POST /adjustments`), transferts (`POST /transfers`), soldes courants (`GET /balances`) et historique (`GET /movements`). Les quantités sont stockées avec trois décimales, les coûts unitaires avec quatre décimales et les valeurs avec deux décimales. Tous les calculs emploient `Decimal`; les valeurs sont arrondies selon `ROUND_HALF_UP` au niveau de leur précision métier.

Chaque mouvement est append-only et alimente un solde unique par couple **produit–entrepôt**. La réception recalcule le coût moyen pondéré, tandis que les sorties, ajustements sortants et transferts consomment ce coût moyen. Les soldes ne peuvent jamais devenir négatifs. Les transferts créent exactement deux mouvements corrélés, `TRANSFER_OUT` et `TRANSFER_IN`, reliés par un même identifiant de transfert ; la source et la destination doivent être différentes. Les soldes concernés sont verrouillés transactionnellement et dans un ordre déterministe afin de prévenir les pertes de mise à jour et les interblocages.

Les permissions `inventory_product:*`, `inventory_warehouse:*` et `inventory_stock:*` séparent les référentiels, les consultations et les opérations physiques. Ce premier périmètre ne génère pas encore d’écritures comptables automatiques, ne gère pas les lots ou numéros de série et applique une valorisation au coût moyen pondéré plutôt qu’une méthode FIFO.

## Gestion Facturation

Le module Facturation gère les factures commerciales tenant-scopées sous `/api/v1/invoicing/invoices`. Une facture contient au moins une ligne, un numéro unique par organisation, un client figé, une date et une échéance optionnelle. Chaque ligne peut référencer un produit actif et un taux TVA actif à la date de facture ; elle préserve toutefois sa description, son prix, son taux et ses montants calculés pour garantir la traçabilité historique.

Les lignes calculent le sous-total comme **quantité × prix unitaire**, puis la TVA selon le taux applicable, avec des montants `Decimal` arrondis au centime par `ROUND_HALF_UP`. Les contrôles de base vérifient que **total de ligne = sous-total + TVA**, que **total de facture = sous-total + TVA**, et que **paiements + avoirs ≤ total de facture**. Les quantités portent trois décimales ; les prix, montants et taux conservent les précisions cohérentes avec les modules Inventaire et TVA.

Une facture débute au statut `DRAFT`. Seul un brouillon peut être modifié ou émis par `POST /api/v1/invoicing/invoices/{invoice_id}/issue`. Après émission, les règlements sous `/api/v1/invoicing/payments` et les avoirs sous `/api/v1/invoicing/credit-notes` sont plafonnés au solde exigible et verrouillent la facture pendant leur application. Le cycle de vie évolue vers `ISSUED`, `PARTIALLY_PAID`, `PAID` ou `CANCELLED` lorsqu’un avoir couvre intégralement une facture non encaissée.

Les permissions `invoice:create`, `invoice:read`, `invoice:update`, `invoice:issue`, `payment:create`, `payment:read`, `credit_note:create` et `credit_note:read` séparent la consultation, l’émission et les opérations de règlement. Ce premier périmètre ne génère pas encore automatiquement les écritures comptables, les sorties de stock ni les factures électroniques, et n’intègre aucun prestataire de paiement externe ; ces intégrations restent explicitement à construire.

## Qualité et sécurité

Exécutez les contrôles avant chaque proposition de changement :

```bash
# Tests
poetry run pytest -q

# Vérification de formatage et lint
poetry run ruff format --check backend
poetry run ruff check backend

# Audit des dépendances de l’environnement local
poetry run pip-audit --local --strict

# Vérification de la configuration Poetry
poetry check
```

Les workflows GitHub Actions exécutent ces mêmes contrôles sur les branches principales et les demandes de fusion. Le fichier `poetry.lock` est versionné afin de garantir la reproductibilité des installations.

## Contribution

Créez une branche dédiée, conservez les changements limités à un objectif cohérent, ajoutez les tests correspondant au comportement modifié et vérifiez les quatre commandes de qualité ci-dessus avant d’ouvrir une demande de fusion.

Pour les changements de schéma, ajoutez une migration Alembic versionnée et testez-la sur une base de données vierge ainsi que sur une base contenant des données représentatives.

## Roadmap technique

La prochaine priorité est de compléter ce vertical par les annulations d’écritures, les soldes comparatifs, les rapprochements partiels, les imports de relevés au format bancaire et l’exécution des migrations sur un environnement PostgreSQL intégré. Les prochains domaines sont la trésorerie, la paie, les immobilisations et l’audit ; chacun sera ajouté progressivement avec sa migration, ses règles métier, ses tests et sa demande de fusion dédiée. Les évolutions Inventaire et Facturation comprendront ensuite les écritures comptables automatiques, la gestion des lots, les numéros de série, les factures électroniques et les intégrations de paiement.
