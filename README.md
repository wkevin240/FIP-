# FIP — Financial, Inventory and Payroll System

FIP est le socle backend d’un système financier modulaire destiné aux flux de comptabilité, inventaire, paie, trésorerie, facturation et audit dans un contexte OHADA. Le projet est développé en Python avec FastAPI, SQLAlchemy asynchrone et PostgreSQL.

> **État actuel.** Cette révision constitue un socle de développement. Les fonctionnalités exposées couvrent le référentiel comptable, les exercices et périodes fiscales, les journaux, les écritures équilibrées, la clôture contrôlée des périodes, le reporting financier de base et professionnel SYSCOHADA, le rapprochement bancaire, la gestion TVA, les verticaux Inventaire, Facturation, Trésorerie, Paie, Immobilisations et Audit transversal. Les autres domaines présents dans l’arborescence sont en cours d’implémentation et ne doivent pas être considérés comme livrés.

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
| Bilan, compte de résultat, balance, grand livre et comparatifs | `/api/v1/accounting/reports` |
| Mapping SYSCOHADA, balance professionnelle, états, réconciliation et export CSV | `/api/v1/accounting/professional-reports` |
| Tableau de flux de trésorerie comptable | `/api/v1/accounting/cash-flow` |
| Rapprochement bancaire | `/api/v1/accounting/bank-reconciliation` |
| Gestion TVA | `/api/v1/accounting/vat` |
| Produits Inventaire | `/api/v1/inventory/products` |
| Entrepôts Inventaire | `/api/v1/inventory/warehouses` |
| Mouvements et soldes de stock | `/api/v1/inventory/stock` |
| Factures commerciales | `/api/v1/invoicing/invoices` |
| Avoirs commerciaux | `/api/v1/invoicing/credit-notes` |
| Règlements de facture | `/api/v1/invoicing/payments` |
| Profils de comptes bancaires Trésorerie et positions | `/api/v1/treasury/bank-accounts` |
| Transactions de relevé Trésorerie et candidats | `/api/v1/treasury/transactions` |
| Validation de rapprochement Trésorerie | `/api/v1/treasury/reconciliation` |
| Salariés et contrats Paie | `/api/v1/payroll/employees` |
| Règles datées et profils comptables Paie | `/api/v1/payroll/configuration` |
| Périodes, entrées, bulletins et comptabilisation Paie | `/api/v1/payroll/periods` |
| Corrections contrôlées de bulletins | `/api/v1/payroll/slips/{payroll_slip_id}/corrections` |
| Profils comptables et catégories Immobilisations | `/api/v1/fixed-assets/configuration` |
| Registre, acquisition et mise en service | `/api/v1/fixed-assets/assets` |
| Plans et dotations d’amortissement | `/api/v1/fixed-assets/depreciation` |
| Cessions et sorties d’immobilisations | `/api/v1/fixed-assets/disposals` |
| Journal Audit et vérification d’intégrité | `/api/v1/audit/events`, `/api/v1/audit/integrity` |

Les routes métier requièrent une authentification et les permissions associées au rôle de l’organisation active.

## Journaux et écritures équilibrées

Un journal est créé au sein d’une organisation, avec un code unique. Une écriture doit être rattachée à un journal actif et à une période fiscale ouverte. Elle comporte au minimum deux lignes ; chaque ligne est exclusivement au débit ou au crédit, et le total des débits doit être exactement égal au total des crédits.

L’écriture est d’abord créée au statut `DRAFT`. L’opération `POST /api/v1/accounting/journal-entries/{journal_entry_id}/post` effectue une seconde vérification des comptes, de la période et de l’équilibre, puis la passe au statut `POSTED`. Une écriture déjà comptabilisée ne peut pas être comptabilisée une seconde fois.

Le lot P0 ajoute une défense structurelle PostgreSQL : journal, période, écriture, ligne et compte doivent appartenir à la même `organization_id`; une référence inter-organisation est refusée par des clés étrangères composites. Toute écriture `POSTED` ou `VOIDED`, ainsi que ses lignes, est immuable et non supprimable au niveau PostgreSQL. Les écritures sont créées `DRAFT` et la transition autorisée vers `POSTED` reste contrôlée par le service comptable, la période ouverte et l’équilibre des lignes. Les tests PostgreSQL réels vérifient ces refus et le fonctionnement inchangé du flux `DRAFT → POSTED`.

La migration P0 crée deux rôles propriétaires non connectables : `fip_database_owner` détient la base et le schéma `public`, tandis que `fip_accounting_owner` détient les tables Accounting. Le rôle applicatif ne possède ni la base ni le schéma, ne peut pas créer d’objets dans `public` et ne détient aucun droit direct de `UPDATE` ou `DELETE` sur les écritures et leurs lignes. La comptabilisation passe par une procédure PostgreSQL `SECURITY DEFINER` qui exige un secret `ACCOUNTING_POSTING_TOKEN`, conservé uniquement sous forme de hachage dans la base. Une variable de session seule, notamment l’ancienne `fip.posting_entry_id`, ne peut donc pas autoriser une comptabilisation. Les fonctions de déclencheur qualifient explicitement les tables sensibles afin qu’un `search_path` contrôlé ne puisse pas substituer les objets Accounting. Les migrations doivent être exécutées avec un rôle distinct, configuré par `POSTGRES_MIGRATION_USER` et `POSTGRES_MIGRATION_PASSWORD`, capable de gérer le schéma et les rôles; le rôle applicatif `POSTGRES_USER` reste restreint.

## Clôture de période

Avant toute clôture, `GET /api/v1/accounting/period-closings/periods/{fiscal_period_id}/preview` calcule le nombre d’écritures et de lignes comptabilisées, les totaux débit/crédit et une empreinte SHA-256 déterministe. La clôture via `POST /api/v1/accounting/period-closings/periods/{fiscal_period_id}` est réservée à la permission `fiscal_period:close`.

La fermeture s’exécute dans une transaction avec verrouillage de la période. Elle refuse les périodes non ouvertes, tout brouillon résiduel et toute écriture comptabilisée individuellement déséquilibrée. À succès, elle persiste d’abord les agrégats et l’empreinte de contrôle dans un registre unique, puis passe la période à `CLOSED`. PostgreSQL impose que les périodes soient créées ouvertes dans un exercice ouvert, ne se chevauchent pas pour un même exercice et ne puissent devenir `CLOSED` qu’après la persistance de ce registre de clôture.

## Reporting financier

Le bilan est disponible via `GET /api/v1/accounting/reports/balance-sheet?as_of_date=YYYY-MM-DD`. Il agrège uniquement les lignes d’écritures `POSTED` jusqu’à la date demandée. Les actifs sont présentés selon `débit − crédit`, tandis que les passifs et capitaux propres suivent `crédit − débit`. Le résultat courant, calculé comme produits moins charges, est inclus dans les capitaux propres ; le rapport est refusé si l’égalité **Actif = Passif + Capitaux propres** n’est pas respectée.

Le compte de résultat est disponible via `GET /api/v1/accounting/reports/income-statement?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`. Il limite strictement les mouvements à l’intervalle inclusif fourni et calcule le résultat net comme **Produits − Charges**. Les deux routes exigent la permission `financial_report:read`.

## Reporting professionnel OHADA/SYSCOHADA

Le socle professionnel sous `/api/v1/accounting/professional-reports` ajoute une balance générale par soldes d’ouverture, mouvements et clôture, un mapping de présentation tenant-scopé du référentiel `SYSCOHADA`, des états groupés, une réconciliation de lecture, un export CSV audité et un paquet JSON SYSCOHADA structuré. Tous les calculs reposent exclusivement sur les écritures `POSTED` et utilisent `Decimal` ; les soldes d’ouverture, les mouvements et les soldes de clôture sont chacun contrôlés à l’égalité **débit = crédit**.

La création d’un mapping exige un compte actif de la même organisation et la permission `professional_reporting:configure`. PostgreSQL impose la référence tenant-scopée au compte par clé étrangère composite. La lecture, la réconciliation et l’export exigent `professional_reporting:read`; la configuration et les exports produisent des événements dans le journal Audit. Le paquet `/exports/syscohada-package.json` est refusé tant que le mapping ou la réconciliation sont incomplets. La liasse de préparation est disponible sous `/api/v1/accounting/syscohada-liasse/` : elle retourne explicitement `NOT_READY` si aucune écriture comptabilisée n’existe et `INCOMPLETE` lorsqu’une configuration est manquante, sans inventer de montant. La documentation détaillée est disponible dans [`docs/accounting_professional_reporting_ohada.md`](docs/accounting_professional_reporting_ohada.md), [`docs/accounting_syscohada_structured_exports.md`](docs/accounting_syscohada_structured_exports.md) et [`docs/accounting_syscohada_liasse_notes.md`](docs/accounting_syscohada_liasse_notes.md).

## Déclarations TVA par période

La TVA peut désormais être consolidée sous forme de déclaration tenant-scopée pour une période fiscale clôturée. FIP agrège uniquement les écritures TVA déjà enregistrées et refuse une seconde déclaration de la même période. Les routes `/api/v1/accounting/vat/declarations` permettent la création, la consultation, la soumission et l’export JSON, avec trace Audit à chaque opération. Aucun taux, compte, écriture ou déclaration de démonstration n’est créé. Les détails sont documentés dans [`docs/accounting_vat_declaration_workflow.md`](docs/accounting_vat_declaration_workflow.md).

## Tableau de flux de trésorerie comptable

Le tableau de flux disponible sous `/api/v1/accounting/cash-flow/statement` classe les mouvements de comptes de trésorerie configurés en exploitation, investissement ou financement. Il reconstruit le solde de clôture à partir du solde d’ouverture et des flux comptabilisés, exclusivement en `Decimal` et à partir d’écritures `POSTED`. Une contrepartie non configurée reste explicitement `UNCLASSIFIED` : l’état peut alors être réconcilié tout en étant signalé incomplet, plutôt que de classer arbitrairement l’opération.

La configuration tenant-scopée sous `/api/v1/accounting/cash-flow/mappings` impose un compte de trésorerie actif de type `ASSET`, ou une catégorie de flux valide. Les mappings utilisent une clé étrangère composite `organization_id`–`account_id` et produisent un événement Audit corrélé. Les permissions `cash_flow:configure` et `cash_flow:read` séparent le paramétrage de la consultation. Consultez [`docs/accounting_cash_flow_statement.md`](docs/accounting_cash_flow_statement.md) pour la méthode et les limites explicites.

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

## Gestion Paie

Le module Paie couvre les salariés et contrats datés, les éléments variables, les jeux de règles réglementaires versionnés par date d’effet, les profils comptables, les périodes et les bulletins. Les paramètres de retenues, cotisations, plafonds, abattements et tranches progressives sont enregistrés au niveau organisation et versionnés : **aucun taux réglementaire n’est codé en dur dans le moteur de calcul**. Cette conception permet d’appliquer une nouvelle réglementation à partir d’une date donnée, tout en conservant les paramètres et lignes de calcul ayant produit chaque bulletin historique.

Une période suit strictement le cycle `DRAFT → CALCULATED → VALIDATED → LOCKED → POSTED`. Seul un brouillon peut recevoir une entrée variable ; une transition ne peut être ni sautée ni inversée. Le moteur calcule le brut, les cotisations salarié et employeur éventuellement plafonnées, l’assiette fiscale annuelle, l’impôt progressif, les retenues diverses et le net à payer exclusivement avec `Decimal` et `ROUND_HALF_UP`. Chaque bulletin conserve des lignes de calcul figées et les totaux de période sont contrôlés au niveau de la base de données.

La comptabilisation `POST /api/v1/payroll/periods/{payroll_period_id}/post` exige une période de paie verrouillée, un exercice fiscal ouvert, un journal actif et des comptes actifs de la même organisation. Elle délègue la création et la comptabilisation de l’écriture équilibrée au module Accounting : charges salariales et patronales au débit, puis dettes envers salariés, administrations fiscales, organismes sociaux et autres retenues au crédit. Toute opération sensible est append-only dans `payroll_audit_events`, avec auteur, horodatage, objet, état avant/après et motif. Après validation, une correction ne peut être demandée que par le mécanisme explicite de correction ; elle ne modifie jamais silencieusement un bulletin validé ou comptabilisé.

Les permissions `payroll_employee:*`, `payroll_contract:*`, `payroll_rule_set:*`, `payroll_period:*`, `payroll_slip:read`, `payroll_correction:create` et `payroll_audit:read` séparent la configuration, la saisie, le calcul, la validation, le verrouillage, la comptabilisation, les corrections et la consultation. La CI exécute la suite rapide SQLite et, dans un job distinct, applique toutes les migrations sur PostgreSQL puis exécute les tests d’intégration Paie contre le moteur cible.

## Gestion Immobilisations

Le module Immobilisations gère les profils comptables, catégories, actifs, composants et plans d’amortissement sous `/api/v1/fixed-assets`. Chaque actif appartient à une organisation, reçoit un code unique, conserve son coût d’entrée, sa valeur résiduelle, ses dates d’acquisition et de mise en service, et suit le cycle strict `DRAFT → ACQUIRED → IN_SERVICE → DISPOSED`. Les composants possèdent leur propre coût, durée d’utilité, méthode et plan afin de préserver les rythmes de consommation distincts.

Le moteur utilise uniquement `Decimal` avec `ROUND_HALF_UP`. Il génère un échéancier mensuel `MONTHLY_PRORATA_DIE` reproductible à partir de la mise en service, du coût, de la valeur résiduelle et des paramètres figés dans le plan. Les méthodes `STRAIGHT_LINE` et `DECLINING_BALANCE` sont configurables ; le dernier montant est ajusté de manière déterministe afin que le cumul égale exactement la base amortissable et que la valeur nette comptable atteigne, sans la franchir, la valeur résiduelle. Aucun taux, durée ou règle réglementaire n’est codé en dur.

L’acquisition, la dotation et la sortie délèguent leurs écritures équilibrées au moteur Accounting. Elles exigent un journal et des comptes actifs de la même organisation ainsi qu’une période fiscale ouverte. Une sortie fige le coût, l’amortissement cumulé, la valeur nette comptable et le gain ou la perte ; elle est bloquée tant que les dotations échues ne sont pas comptabilisées. Les événements sensibles sont ajoutés au registre append-only `fixed_asset_audit_events`, sans route de modification ni suppression.

Les permissions `fixed_asset_category:*`, `fixed_asset:*`, `fixed_asset_depreciation:*` et `fixed_asset_disposal:create` séparent la configuration, le registre, la dotation et les sorties. Les migrations et les contraintes sont testées sur PostgreSQL en plus des tests unitaires du moteur de calcul et du contrôle OpenAPI.

## Journal Audit transversal

Le journal Audit transversal expose exclusivement des ressources de consultation sous `/api/v1/audit`. Chaque événement est isolé par `organization_id`, ordonné par une séquence strictement croissante, daté avec précision, associé lorsque disponible à son auteur, à son action, à sa ressource, à ses valeurs avant/après, à son contexte et à son identifiant de transaction. La recherche paginée accepte les filtres d’action, de ressource, d’auteur, de transaction et d’intervalle temporel ; aucune route métier ne permet de créer, modifier ou supprimer un événement directement.

Chaque organisation possède une tête de chaîne verrouillée pendant l’ajout. Un événement inclut le hachage SHA-256 de son prédécesseur et son propre hachage calculé sur une représentation canonique des données. L’endpoint `GET /api/v1/audit/integrity` recalcule la séquence et les hachages afin de détecter une rupture. Sur PostgreSQL, les déclencheurs `BEFORE UPDATE` et `BEFORE DELETE` interdisent toute mutation ou suppression directe du registre. Les événements sont écrits dans la même session SQLAlchemy que l’opération métier ; un rollback de cette transaction annule donc également l’événement associé.

Les écritures comptables créées ou comptabilisées, les comptes créés ou modifiés, ainsi que les événements locaux de Paie et Immobilisations alimentent le registre transversal. Les permissions `audit_event:read` et `audit_event:verify` séparent la consultation de la vérification ; elles ne confèrent jamais de capacité de mutation. Les index couvrent les recherches récurrentes par organisation, date, action, ressource, auteur et transaction.

## Gestion Trésorerie

Le module Trésorerie introduit un **profil bancaire opérationnel** sous `/api/v1/treasury/bank-accounts`, sans dupliquer les comptes bancaires ni les rapprochements du domaine Comptabilité. Chaque profil appartient à une organisation et référence un unique compte comptable actif de type `ASSET`. Le numéro de compte bancaire et le compte comptable associé sont tous deux uniques dans l’organisation. Le profil conserve l’établissement, la devise, le solde et la date d’ouverture, et peut être désactivé sans effacer son historique.

La position disponible via `GET /api/v1/treasury/bank-accounts/{treasury_bank_account_id}/position` compare deux bases calculées en `Decimal` : le solde relevé, égal au solde d’ouverture augmenté des transactions bancaires depuis la date d’ouverture, et le solde grand livre, égal au solde d’ouverture augmenté des mouvements `débit − crédit` d’écritures `POSTED` sur le compte associé. La réponse expose l’écart de rapprochement, le montant des transactions encore non rapprochées et leur nombre afin de rendre les différences traçables.

Les opérations de relevé et de rapprochement restent la **source de vérité unique** du domaine comptable, dans les ressources existantes de transactions et rapprochements bancaires. Les façades Trésorerie importent une transaction avec `POST /api/v1/treasury/transactions/`, la consultent par profil avec `GET /api/v1/treasury/transactions/bank-accounts/{treasury_bank_account_id}`, proposent les écritures candidates et valident le rapprochement sous `/api/v1/treasury/reconciliation`. Elles imposent un profil actif, filtrent toute donnée par organisation, compte comptable et date d’ouverture, et refusent l’utilisation d’une transaction appartenant à un autre profil bancaire.

Les permissions `treasury_bank_account:create`, `treasury_bank_account:read`, `treasury_bank_account:update`, `treasury_position:read`, `treasury_transaction:create`, `treasury_transaction:read`, `treasury_reconciliation:read` et `treasury_reconciliation:match` séparent la configuration, la consultation de position, l’import et la validation. Ce premier périmètre ne fournit pas encore de prévision de trésorerie, de rapprochement partiel ni d’import de fichiers de relevé normalisés ; ces capacités restent des évolutions distinctes.

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

Les workflows GitHub Actions exécutent ces mêmes contrôles sur les branches principales et les demandes de fusion. Un job PostgreSQL séparé applique la chaîne Alembic complète puis lance les tests d’intégration des modules Paie, Immobilisations et Audit contre le moteur cible. Le fichier `poetry.lock` est versionné afin de garantir la reproductibilité des installations.

## Contribution

Créez une branche dédiée, conservez les changements limités à un objectif cohérent, ajoutez les tests correspondant au comportement modifié et vérifiez les quatre commandes de qualité ci-dessus avant d’ouvrir une demande de fusion.

Pour les changements de schéma, ajoutez une migration Alembic versionnée et testez-la sur une base de données vierge ainsi que sur une base contenant des données représentatives.

## Roadmap technique

La prochaine priorité est de compléter les verticaux livrés par les annulations d’écritures, les soldes comparatifs, les rapprochements partiels et les imports de relevés au format bancaire. La prochaine priorité métier est le durcissement du moteur Accounting : contre-passations contrôlées, corrections et immutabilité des écritures `POSTED`, balance générale, grand livre et soldes comparatifs. Suivront les rapprochements partiels/groupés, les imports bancaires normalisés, l’extension des états OHADA/SYSCOHADA (notes annexes et liasse), la validation PostgreSQL complète et le durcissement sécurité/production avant tout pipeline de déploiement. Chaque évolution sera ajoutée progressivement avec sa migration, ses règles métier, ses tests et sa demande de fusion dédiée. Les évolutions Paie comprendront ensuite l’approbation et l’application des corrections, les exports de bulletins et les déclarations réglementaires paramétrables. Les évolutions Inventaire et Facturation comprendront les écritures comptables automatiques, la gestion des lots, les numéros de série, les factures électroniques et les intégrations de paiement.
