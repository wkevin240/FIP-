# FIP - Financial Operating System

> **Financial, Inventory & Payroll System** — Système modulaire multi-organisations conforme OHADA

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table des matières

1. [Aperçu](#aperçu)
2. [Fonctionnalités](#fonctionnalités)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Démarrage](#démarrage)
7. [API Endpoints](#api-endpoints)
8. [Développement](#développement)
9. [Déploiement](#déploiement)
10. [License](#license)

---

## Aperçu

FIP est un système ERP (Enterprise Resource Planning) modulaire conçu pour les entreprises africaines opérant sous le référentiel OHADA.

Le système couvre l'ensemble des domaines financiers, comptables et administratifs :

- **Comptabilité** — Plan OHADA, écritures, lettrage, clôture
- **Immobilisations** — Gestion, amortissement, cession
- **Paie** — Employés, bulletins, charges sociales
- **Trésorerie** — Banques, opérations, rapprochement
- **Facturation** — Clients, fournisseurs, TVA
- **Inventaire** — Produits, stocks, entrepôts

---

## Fonctionnalités

### Module Comptabilité
- Plan comptable OHADA (SYSCOHADA)
- Gestion des exercices et périodes fiscales
- Écritures comptables avec validation
- Rapprochement bancaire
- Clôture d'exercice
- Génération des états financiers

### Module Immobilisations
- Suivi des actifs corporels et incorporels
- Calculs d'amortissement (linéaire, dégressif)
- Cession et mise au rebut
- Amortissement dérogatoire

### Module Paie
- Gestion des employés et contrats
- Bulletins de paie
- Charges sociales (CNPS, IRPP)
- Déclarations sociales

### Module Trésorerie
- Gestion multi-banques
- Opérations de trésorerie
- Rapprochement bancaire automatique

### Module Facturation
- Facturation clients et fournisseurs
- Gestion de la TVA
- Notes de crédit
- Suivi des paiements

### Module Inventaire
- Gestion des produits
- Suivi des stocks
- Multi-entrepôts
- Mouvements de stock

---

## Architecture

FIP adopte l'architecture **Clean Architecture** avec une séparation stricte des responsabilités.

```
backend/
├── app/
│   ├── api/              # Couche API (FastAPI routes)
│   │   └── v1/
│   │       ├── accounting/   # Endpoints comptabilité
│   │       ├── fixed_assets/ # Endpoints immobilisations
│   │       ├── inventory/   # Endpoints inventaire
│   │       ├── invoicing/   # Endpoints facturation
│   │       ├── payroll/     # Endpoints paie
│   │       └── treasury/    # Endpoints trésorerie
│   │
│   ├── core/             # Configuration, sécurité, exceptions
│   │   ├── config.py
│   │   ├── security.py
│   │   └── exceptions.py
│   │
│   ├── db/               # Couche base de données
│   │   ├── migrations/   # Migrations Alembic
│   │   ├── session.py
│   │   └── base.py
│   │
│   ├── domain/           # Couche domaine (règles métier)
│   │   ├── accounting/
│   │   ├── fixed_assets/
│   │   ├── inventory/
│   │   ├── invoicing/
│   │   ├── payroll/
│   │   ├── shared/       # Value objects, events
│   │   └── treasury/
│   │
│   ├── repositories/     # Couche persistance
│   ├── schemas/         # Schémas Pydantic (DTOs)
│   ├── services/        # Couche application
│   └── audit/           # Audit et traçabilité
│
├── docs/                 # Documentation
│   ├── accounting/
│   ├── architecture/
│   └── development/
│
├── scripts/             # Scripts utilitaires
├── deployments/         # Configs déploiement
└── tests/              # Tests
```

### Principes architecturaux

1. **Séparation des préoccupations** — Chaque couche a une responsabilité unique
2. **Dépendances unidirectionnelles** — Les couches internes ne dépendent pas des couches externes
3. **Inversion de contrôle** — Les dépendances sont injectées
4. **Isolation du domaine** — Les règles métier sont dans la couche domaine

---

## Installation

### Prérequis

- Python 3.11+
- PostgreSQL 15+
- Git

### Cloner le projet

```bash
git clone https://github.com/wkevin240/FIP-.git
cd FIP-
```

### Créer un environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

Ou avec Poetry :

```bash
poetry install
```

---

## Configuration

### Variables d'environnement

Créer un fichier `.env` à la racine du backend :

```env
# Application
PROJECT_NAME="FIP - Financial, Inventory and Payroll System"
VERSION="1.0.0"
API_V1_STR="/api/v1"

# Base de données
POSTGRES_SERVER=localhost
POSTGRES_USER=fip_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=fip_db
POSTGRES_PORT=5432

# Sécurité
SECRET_KEY=your-very-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=11520

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
```

### Configuration de la base de données

1. Créer l'utilisateur PostgreSQL :

```sql
CREATE USER fip_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE fip_db OWNER fip_user;
```

2. Appliquer les migrations :

```bash
cd backend
alembic upgrade head
```

---

## Démarrage

### Mode développement

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera accessible sur : http://localhost:8000

### Mode production

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Documentation API

Une fois le serveur démarré :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **OpenAPI JSON** : http://localhost:8000/api/v1/openapi.json

---

## API Endpoints

### Santé

```
GET /health
```

### Comptabilité

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/accounting/accounts` | Liste des comptes |
| POST | `/api/v1/accounting/accounts` | Créer un compte |
| GET | `/api/v1/accounting/accounts/{id}` | Détail d'un compte |
| PUT | `/api/v1/accounting/accounts/{id}` | Modifier un compte |
| DELETE | `/api/v1/accounting/accounts/{id}` | Supprimer un compte |
| GET | `/api/v1/accounting/fiscal-years` | Exercices fiscaux |
| GET | `/api/v1/accounting/fiscal-periods` | Périodes fiscales |

*Liste complète dans `/docs/api/API_REFERENCE.md`*

---

## Développement

### Structure des commits

Nous suivons [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajoute le module de facturation
fix: corrige le calcul de TVA
docs: met à jour le README
refactor: restructure le service comptable
test: ajoute les tests du module paie
```

### Règles de code

- Follow PEP 8
- Type hints obligatoires
- Docstrings Google style
- Max line length: 88 (Black)

### Tests

```bash
# Tous les tests
pytest

# Avec couverture
pytest --cov=app --cov-report=html

# Tests spécifiques
pytest tests/unit/
pytest tests/integration/
```

---

## Déploiement

### Docker

```bash
# Build de l'image
docker build -t fip-backend .

# Lancement avec Docker Compose
docker-compose up -d
```

### Configuration production

Voir `/docs/development/DEPLOYMENT.md` pour les détails sur :

- Nginx + Gunicorn
- Configuration HTTPS
- Monitoring (Prometheus, Grafana)
- Backup automatique

---

## Stack technique

| Composant | Technologie |
|-----------|------------|
| Backend | FastAPI, Python 3.11+ |
| ORM | SQLAlchemy 2.0 (async) |
| Base de données | PostgreSQL 15+ |
| Migrations | Alembic |
| Authentification | JWT (HS256) |
| Validation | Pydantic v2 |
| Cache | Redis (optionnel) |
| Queue | Celery (optionnel) |
| API | REST |
| Documentation | OpenAPI 3.0 |

---

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## Contact

- **Auteur** : Kevin WANSI
- **GitHub** : [@wkevin240](https://github.com/wkevin240)
- **Email** : à configurer

---

*FIP — Le système financier nouvelle génération pour l'Afrique*
