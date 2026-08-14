# Reporting comptable professionnel OHADA/SYSCOHADA

## Objectif et périmètre

Ce lot ajoute un socle de reporting professionnel tenant-scopé fondé exclusivement sur les écritures comptables au statut `POSTED`. Il introduit une balance générale complète, un mapping paramétrable de présentation SYSCOHADA, des états de présentation contrôlés, une réconciliation de lecture et un export CSV audité.

L’AUDCIF, auquel est annexé le SYSCOHADA révisé, organise notamment le plan des comptes, la tenue des comptes et la présentation des états financiers [1]. Le produit ne code donc pas un plan de comptes unique en dur : chaque organisation configure son propre mapping, ce qui préserve l’adaptation au plan réellement employé et rend la présentation traçable.

## Mapping tenant-scopé

Une règle de `financial_statement_mappings` associe un compte actif de l’organisation à une rubrique de présentation dans le référentiel `SYSCOHADA`. La clé étrangère composite `(organization_id, account_id)` garantit au niveau PostgreSQL qu’une règle ne peut pas référencer le compte d’une autre organisation. Une même organisation ne peut configurer qu’une règle par compte, référentiel et état.

| État | Rôles de présentation admis | Validation métier |
|---|---|---|
| `BALANCE_SHEET` | `ASSETS`, `LIABILITIES_EQUITY` | Les comptes `ASSET` alimentent `ASSETS`. Les passifs, capitaux propres, produits et charges alimentent `LIABILITIES_EQUITY`, ce qui incorpore le résultat courant. |
| `INCOME_STATEMENT` | `REVENUE`, `EXPENSE` | Les produits et charges sont les seuls comptes mappables. |

La création de mapping exige la permission `professional_reporting:configure`, contrôle que le compte est actif et tenant-scopé, puis écrit un événement `FINANCIAL_STATEMENT_MAPPING_CREATED` dans le journal Audit dans la même transaction.

## États et contrôles

La route `GET /api/v1/accounting/professional-reports/trial-balance` expose une balance par compte et par intervalle : soldes d’ouverture débiteur/créditeur, mouvements débit/crédit et soldes de clôture débiteur/créditeur. Les totaux de chaque niveau doivent respecter les égalités débit = crédit.

Le calcul distingue explicitement les mouvements avant `start_date` et les mouvements inclusifs de l’intervalle `[start_date, end_date]`. Les montants restent des `Decimal`, sans conversion en `float`. Les écritures annulées, les brouillons et les écritures d’autres organisations sont absents des requêtes sources.

Les routes `GET /api/v1/accounting/professional-reports/statements/BALANCE_SHEET` et `GET /api/v1/accounting/professional-reports/statements/INCOME_STATEMENT` produisent des lignes groupées par section et ligne du mapping. La réponse signale explicitement les comptes pertinents encore non mappés ; elle n’invente aucune classification. Le bilan expose `total_assets`, `total_liabilities_and_equity` et `is_balanced`. Le compte de résultat expose `net_result = revenue − expense`.

`GET /api/v1/accounting/professional-reports/reconciliation` vérifie indépendamment l’équilibre ouverture/mouvement/clôture de la balance professionnelle et l’égalité du bilan générique. Il sert de point de contrôle de lecture entre les écritures source et les états.

## Export et Audit

`GET /api/v1/accounting/professional-reports/trial-balance/export.csv` produit un CSV à en-tête stable depuis le même service de calcul que l’API de balance. Il ajoute l’événement Audit `PROFESSIONAL_TRIAL_BALANCE_EXPORTED`, incluant l’intervalle implicite dans l’identifiant de ressource, le format et le nombre de lignes exportées. Un échec transactionnel ne doit laisser aucune trace d’export.

| Opération | Permission | Trace Audit |
|---|---|---|
| Lire les états professionnels | `professional_reporting:read` | Aucune écriture d’Audit de lecture simple |
| Configurer un mapping | `professional_reporting:configure` | `FINANCIAL_STATEMENT_MAPPING_CREATED` |
| Exporter la balance CSV | `professional_reporting:read` | `PROFESSIONAL_TRIAL_BALANCE_EXPORTED` |

## Sécurité PostgreSQL

La migration `0013_professional_reporting` est chaînée après le durcissement P1. Elle attribue la table au rôle non connectable `fip_accounting_owner`, révoque tout droit public, et accorde au seul rôle applicatif `fip_user` les droits `SELECT`, `INSERT`, `UPDATE`, `DELETE` nécessaires à la configuration. Le rôle applicatif ne devient pas propriétaire de la base ni du schéma.

Les tests PostgreSQL réels vérifient le propriétaire, les privilèges applicatifs et l’échec d’une insertion directe de mapping qui tente de rattacher un compte d’une organisation à une autre organisation.

## Limites assumées de cet incrément

Ce socle ne produit pas encore les notes annexes exhaustives, un tableau de flux de trésorerie SYSCOHADA complet, les comptes consolidés ou combinés, les états IFRS, ni un format de liasse réglementaire propre à chaque autorité nationale. Ces éléments nécessitent des données et modèles supplémentaires et devront faire l’objet de lots séparés, sans contourner les invariants de ce document.

## Référence

[1] [OHADA — Acte uniforme relatif au droit comptable et à l’information financière (AUDCIF)](https://www.ohada.org/en/uniform-act-relating-to-accounting-law-and-financial-information-audcif/)
