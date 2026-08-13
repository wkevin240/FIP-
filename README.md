# FIP — Financial, Inventory and Payroll System

FIP est le socle backend d’un système financier modulaire destiné aux flux de comptabilité, inventaire, paie, trésorerie, facturation et audit dans un contexte OHADA. Le projet est développé en Python avec FastAPI, SQLAlchemy asynchrone et PostgreSQL.

> **État actuel.** Cette révision constitue un socle de développement. Les fonctionnalités actuellement exposées concernent le référentiel comptable, les exercices fiscaux et les périodes fiscales. Les autres domaines présents dans l’arborescence sont en cours d’implémentation et ne doivent pas être considérés comme livrés.

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

Les routes métier requièrent une authentification et les permissions associées au rôle de l’organisation active.

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

La priorité est d’achever un premier vertical comptable vérifiable de bout en bout : référentiel de comptes, journaux, écritures équilibrées, périodes clôturées et rapports. Les domaines de stock, paie, trésorerie, immobilisations et facturation seront ajoutés une fois ce socle validé par des tests d’intégration et des migrations de base de données.
