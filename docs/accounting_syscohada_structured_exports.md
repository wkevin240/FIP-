# Export structuré des états professionnels SYSCOHADA

## Objectif

Cet incrément ajoute un paquet JSON structuré destiné à l’échange, à l’archivage et à la préparation de restitutions SYSCOHADA. Il ne recalcule aucune donnée : il assemble les résultats déjà contrôlés de la balance professionnelle, du bilan professionnel, du compte de résultat et de la réconciliation Accounting.

L’export est disponible par `GET /api/v1/accounting/professional-reports/exports/syscohada-package.json`, avec la permission `professional_reporting:read`.

## Contenu et déterminisme

Le document contient la version de schéma, le référentiel `SYSCOHADA`, l’organisation, l’intervalle, les contrôles de réconciliation, la balance professionnelle, le bilan et le compte de résultat. Les dates et les montants `Decimal` sont sérialisés dans un format JSON stable, sans conversion en `float`.

| Section | Source comptable |
|---|---|
| `controls` | Réconciliation de la balance et du bilan professionnel |
| `trial_balance` | Balance ouverture, mouvements et clôture |
| `balance_sheet` | Bilan issu des mappings SYSCOHADA |
| `income_statement` | Compte de résultat issu des mappings SYSCOHADA |

## Garde-fous

La génération est refusée avec `422` si la réconciliation n’est pas cohérente, si le bilan professionnel comporte des comptes non mappés, ou si le compte de résultat comporte des comptes non mappés. Il est donc impossible de présenter un paquet comme complet lorsque sa configuration ne l’est pas.

Une génération réussie écrit `SYSCOHADA_REPORTING_PACKAGE_EXPORTED` dans le journal Audit, dans la même transaction. Une génération refusée ne produit aucune trace Audit.

## Limite explicite

Ce paquet est un **format structuré de préparation réglementaire**, et non encore une liasse fiscale ou une télédéclaration propre à une administration nationale. Les formulaires spécifiques, signatures, identifiants déclaratifs et canaux de dépôt seront livrés dans un lot séparé, sur la base stable de cet export.
