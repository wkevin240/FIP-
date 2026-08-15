# Workflow de déclaration TVA

## Finalité

Ce lot ajoute une déclaration TVA tenant-scopée pour une période fiscale clôturée. Elle agrège exclusivement les écritures `VATEntry` réellement enregistrées sur la période : TVA collectée, TVA déductible et TVA nette à payer. Le système ne crée aucun taux, compte, écriture TVA, période ou déclaration par défaut.

## Workflow

| Étape | Règle |
|---|---|
| Création | La période fiscale doit appartenir à l’organisation et être `CLOSED`. |
| Agrégation | Les montants sont calculés en `Decimal` depuis les écritures TVA de la période. Une période sans écriture produit donc un total réel de `0,00`, non une donnée simulée. |
| Unicité | Une seule déclaration est autorisée par couple organisation-période. |
| Soumission | Une déclaration `READY` devient `SUBMITTED` une seule fois ; la seconde tentative est refusée. |
| Export | Le JSON contient la période, les totaux réels et le statut de la déclaration. |

## API et permissions

| Route | Permission | Action |
|---|---|---|
| `POST /api/v1/accounting/vat/declarations` | `vat:create` | Crée le snapshot de déclaration pour une période clôturée. |
| `GET /api/v1/accounting/vat/declarations` | `vat:read` | Liste les déclarations de l’organisation active. |
| `POST /api/v1/accounting/vat/declarations/{id}/submit` | `vat:update` | Soumet la déclaration une fois. |
| `GET /api/v1/accounting/vat/declarations/{id}/export.json` | `vat:read` | Exporte le snapshot JSON. |

## Audit et protection PostgreSQL

Les opérations réussies écrivent respectivement `VAT_DECLARATION_CREATED`, `VAT_DECLARATION_SUBMITTED` et `VAT_DECLARATION_EXPORTED` dans le journal Audit append-only. La migration `0015_vat_declarations` attribue la table à `fip_accounting_owner`, révoque les droits publics et n’accorde à `fip_user` que les droits applicatifs nécessaires. Elle ne contient ni migration de données ni seed.
