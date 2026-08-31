# Architecture de FIP

## Vue d'ensemble

FIP est construit selon les principes de la **Clean Architecture** (Onion Architecture), garantissant une séparation stricte des préoccupations et une maintenabilité à long terme.

```
                    ┌─────────────────────────────────┐
                    │      Presentation Layer          │
                    │         (FastAPI Routes)         │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │       Application Layer          │
                    │        (Schemas / DTOs)         │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │        Service Layer            │
                    │     (Business Logic)            │
                    └──────────────┬──────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
┌──────────▼──────────┐ ┌─────────▼────────┐ ┌────────▼────────┐
│   Domain Layer       │ │ Repository Layer  │ │  External APIs  │
│  (Business Rules)    │ │   (Data Access)  │ │ (Integrations) │
└─────────────────────┘ └──────────────────┘ └─────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     Infrastructure Layer        │
                    │     (Database, Security)        │
                    └─────────────────────────────────┘
```

## Couches architecturales

### 1. API Layer (`app/api/`)

**Responsabilité** : Exposition des endpoints HTTP, validation des requêtes entrantes.

- Routes FastAPI avec dépendances injectées
- Conversion request/response via Pydantic schemas
- Gestion des erreurs HTTP standardisées
- Documentation OpenAPI automatique

**Règles** :
- Aucune logique métier ici
- Delegates vers les services
- Formatage des réponses

### 2. Schema Layer (`app/schemas/`)

**Responsabilité** : Définition des DTOs (Data Transfer Objects).

- `*Create` — Schémas de création
- `*Update` — Schémas de mise à jour
- `*Response` — Schémas de réponse
- `*Filter` — Schémas de filtrage/pagination

### 3. Service Layer (`app/services/`)

**Responsabilité** : Logique métier applicative.

- Orchestration des opérations
- Validation des règles métier
- Transactions
- Événements de domaine

**Règles** :
- Ne contient pas d'accès direct à la DB
- Utilise les repositories pour la persistance
- Émet des events pour les side effects

### 4. Domain Layer (`app/domain/`)

**Responsabilité** : Règles métier pures, sans dépendances externes.

- Entités (Account, Invoice, Employee...)
- Value Objects (Money, DateRange...)
- Services de domaine (AccountCalculator, DepreciationCalculator...)
- Règles de validation métier
- Événements de domaine

**Règles** :
- Aucune dépendance vers d'autres couches
- Pure Python, pas de framework
- Testable unitairement sans DB

### 5. Repository Layer (`app/repositories/`)

**Responsabilité** : Abstraction de l'accès aux données.

- Interfaces (protocoles Python)
- Implémentations SQLAlchemy
- Requêtes complexes
- Optimisation des performances

### 6. Infrastructure Layer (`app/core/`, `app/db/`)

**Responsabilité** : Configuration, sécurité, accès technique.

- Configuration de l'application
- Connexion à la DB
- Sécurité et authentification
- Logging

## Flux d'une requête

```
HTTP Request
    │
    ▼
┌───────────────┐
│  API Route    │  ← Validation route, extraction params
└───────┬───────┘
        │
    ┌───▼───┐
    │ Schema │  ← Validation Pydantic, conversion DTO
    └───┬───┘
        │
    ┌───▼───┐
    │Service│  ← Logique métier, orchestration
    └───┬───┘
        │
    ┌───▼───┐
    │Domain │  ← Règles métier pures
    └───┬───┘
        │
    ┌───▼───┐
    │Repository│  ← Persistance via SQLAlchemy
    └───┬───┘
        │
    ┌───▼───┐
    │  DB   │  ← PostgreSQL
    └───────┘
```

## Modules métier

### Accounting (`app/domain/accounting/`)

```
accounting/
├── account/
│   ├── entities.py       # Account entity
│   ├── validators.py    # Validation règles OHADA
│   ├── calculators.py   # Soldes, balances
│   └── rules.py         # Règles du SYSCOHADA
├── journal_entry/
├── fiscal_year/
├── fiscal_period/
├── closing/
└── reconciliation/
```

### Fixed Assets (`app/domain/fixed_assets/`)

```
fixed_assets/
├── asset/              # Immobilisation entity
├── depreciation/       # Calcul amortissement
└── disposal/           # Cession
```

### Payroll (`app/domain/payroll/`)

```
payroll/
├── employee/           # Employé entity
├── payroll/            # Bulletin de paie
└── payroll_period/     # Période de paie
```

### Treasury (`app/domain/treasury/`)

```
treasury/
├── bank_account/       # Compte bancaire
├── transaction/        # Opération bancaire
└── reconciliation/     # Rapprochement
```

## Patterns utilisés

### Repository Pattern

```python
class AccountRepository(Protocol):
    async def get_by_id(self, id: str) -> Account | None
    async def get_all(self, skip: int, limit: int) -> list[Account]
    async def create(self, account: Account) -> Account
    async def update(self, id: str, account: Account) -> Account
    async def delete(self, id: str) -> None

class SQLAlchemyAccountRepository:
    def __init__(self, session: AsyncSession)
    async def get_by_id(self, id: str) -> Account | None
    # ...
```

### Service Pattern

```python
class AccountService:
    def __init__(
        self,
        repository: AccountRepository,
        event_bus: EventBus,
    )
    async def create_account(self, data: AccountCreate) -> AccountResponse:
        # 1. Validate input
        # 2. Create domain entity
        # 3. Persist via repository
        # 4. Emit domain event
        # 5. Return response
```

### Event-Driven

```python
@dataclass
class AccountCreatedEvent(DomainEvent):
    account_id: str
    account_code: str
    created_at: datetime

class EventBus:
    async def publish(self, event: DomainEvent) -> None
    # Publishes to audit trail, notifications, etc.
```

## Sécurité

### Authentification

- JWT tokens avec expiration configurable
- Refresh tokens pour renouvellements
- Hash bcrypt pour passwords

### Autorisation

- RBAC (Role-Based Access Control)
- Permissions granulaires
- Isolation par organisation

### Audit

- Toutes les mutations sont journalisées
- Traçabilité complète (who, when, what)
- Events de domaine pour audit trail

## Performance

### Async I/O

- SQLAlchemy async avec asyncpg
- FastAPI natif async
- Connection pooling

### Optimisations

- Index sur les colonnes fréquemment requêtées
- Pagination sur toutes les listes
- Cache Redis (optionnel) pour les données read-heavy

## Testing

```
tests/
├── unit/
│   ├── domain/          # Tests des règles métier
│   ├── services/        # Tests des services
│   └── repositories/    # Tests des repositories
├── integration/
│   └── api/            # Tests des endpoints
└── fixtures/           # Data de test
```

## Extensions futures

- **Multi-tenant** : Isolation complète par organisation
- **Audit trail** : Historique des modifications
- **Notifications** : Email, SMS, webhook
- **Export** : Excel, PDF, CSV
- **API publique** : Pour intégrations tierces

---

*Document mis à jour : 2026-08-31*
