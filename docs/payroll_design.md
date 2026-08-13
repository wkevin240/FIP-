# Conception — Module Paie professionnel

## Objet et périmètre

Le premier vertical Paie gère les salariés, leurs contrats datés, les périodes mensuelles, les éléments de rémunération, les calculs de salaire, les bulletins, les transitions contrôlées et la génération d’écritures comptables. Son objectif est de préserver les mêmes garanties que le moteur Accounting : **isolation par organisation, calculs déterministes en `Decimal`, verrouillage transactionnel, statuts explicites, snapshots historiques et contrôles de cohérence**.

Les paramètres réglementaires ne sont pas codés en dur. Le moteur est donc configurable pour le Cameroun et les règles OHADA, tout en nécessitant une validation réglementaire de l’organisation avant activation d’un jeu en production. Les références institutionnelles consultées sont consignées dans [les notes réglementaires](payroll_cameroon_regulatory_notes.md).

## Agrégat principal et cycle de vie

La **période de paie** constitue l’agrégat opérationnel. Elle porte les dates de travail et de paiement, le jeu de règles applicable, les comptes de comptabilisation et les bulletins calculés.

```text
DRAFT → CALCULATED → VALIDATED → LOCKED → POSTED
```

| État | Autorisations et effet |
|---|---|
| `DRAFT` | Les éléments variables peuvent être saisis, mis à jour ou retirés. |
| `CALCULATED` | Les bulletins et lignes calculées sont figés ; un nouveau calcul remplace explicitement les résultats du brouillon. |
| `VALIDATED` | La période et ses bulletins sont verrouillés contre toute mutation ordinaire. |
| `LOCKED` | La validation est consolidée sous verrou de ligne ; seule la comptabilisation ou une correction contrôlée est possible. |
| `POSTED` | L’écriture Accounting équilibrée est créée et comptabilisée. Aucun changement direct ne reste permis. |

Toute correction après `VALIDATED` crée une demande de correction et un bulletin de correction lié au bulletin d’origine. Elle exige un motif, l’auteur et une nouvelle période ou un flux de correction explicitement autorisé. Une suppression physique d’un bulletin validé, verrouillé ou comptabilisé est interdite.

## Modèle de données proposé

| Table | Responsabilité et invariants principaux |
|---|---|
| `payroll_employees` | Salarié tenant-scopé ; code salarié unique par organisation ; identité, statut actif, identifiant fiscal/social facultatif. |
| `payroll_contracts` | Contrat daté par salarié ; salaire de base mensuel, devise, statut, dates de validité. Les chevauchements de contrats actifs sont refusés par le service. |
| `payroll_rule_sets` | Jeu de paramètres réglementaires versionné, daté et activable ; une période référence le jeu appliqué. |
| `payroll_contribution_rules` | Cotisations salarié/employeur : code unique dans le jeu, assiette, taux, plafond facultatif, direction et ordre de calcul. |
| `payroll_tax_brackets` | Tranches progressives d’un jeu de règles, bornes annuelles et taux ; ordonnées et sans chevauchement au contrôle de service. |
| `payroll_periods` | Agrégat de paie : dates, statut, jeu de règles, profil comptable, totaux, acteurs et horodatages des transitions. |
| `payroll_inputs` | Éléments variables signés de la période : gain ou retenue, description, montant, source et auteur ; modifiables uniquement en `DRAFT`. |
| `payroll_slips` | Bulletin par salarié et période ; un seul bulletin principal par couple période–salarié ; conserve les totaux brut, cotisations, impôt, retenues et net. |
| `payroll_slip_lines` | Lignes immuables de calcul : type, base, taux, plafond, montant, ordre, code de règle et description figée. |
| `payroll_corrections` | Demande de correction traçable : bulletin d’origine, motif, auteur, date, résultat et lien vers le bulletin correctif. |
| `payroll_accounting_profiles` | Mapping tenant-scopé des comptes actifs et du journal : charge de salaire, dette salariale, dette fiscale et dette sociale. |
| `payroll_audit_events` | Événements append-only du module : organisation, acteur, action, type/id d’objet, état précédent, état suivant, motif et horodatage. |

Les montants sont stockés en `Numeric(18, 2)`, les taux en `Numeric(9, 6)`, les plafonds avec la même précision monétaire et les devises sur trois caractères. Les clés étrangères utilisent `RESTRICT` sur les données financières. Les contraintes SQL couvrent au minimum les statuts autorisés, la positivité des montants, la cohérence `net = brut − cotisations salarié − impôt − autres retenues`, l’unicité tenant-scopée et l’unicité période–salarié.

## Algorithme de calcul reproductible

Le domaine pur reçoit exclusivement des contrats, éléments variables et **snapshots de règles déjà datés**. Il renvoie un résultat complet et des lignes de calcul, sans requête SQL ni dépendance HTTP.

1. `brut = salaire_de_base + gains_variables`.
2. Pour chaque cotisation salariale ou patronale, l’assiette est calculée selon le type configuré, plafonnée le cas échéant, puis le montant est arrondi avec `ROUND_HALF_UP` au centime.
3. `retenues_salariales = cotisations_salariales + retenues_variables`.
4. La base imposable est déterminée au moyen des paramètres versionnés : assiette, abattements et cotisations admises. Le barème progressif est appliqué annuellement ou mensuellement selon le jeu de règles, puis ramené à la périodicité et majoré le cas échéant par un paramètre distinct.
5. `net_à_payer = brut − cotisations_salariales − impôt − autres_retenues`.
6. Les coûts employeur sont conservés séparément ; ils ne diminuent jamais le net salarié.

Chaque ligne de bulletin mémorise le code de règle, la base, le taux, le plafond, le montant et l’ordre réellement appliqués. Un changement ultérieur de taux, plafond ou tranche ne réécrit donc jamais une paie antérieure.

## Comptabilisation

La transition `LOCKED → POSTED` s’effectue sous verrou de la période et doit appeler `JournalEntryService.create_entry()` puis `JournalEntryService.post_entry()` ; aucune écriture parallèle n’est créée directement depuis les modèles de paie. Le profil comptable doit désigner un journal actif, une période fiscale ouverte et des comptes actifs de la même organisation.

Le schéma comptable agrégé est le suivant : les charges de salaire et les coûts employeur sont débités ; le net salarié à payer, les impôts retenus et les cotisations dues sont crédités. Les lignes sont agrégées de façon déterministe par compte et le domaine vérifie `total débit = total crédit` avant d’appeler Accounting. La référence d’écriture est unique et dérivée de la période ; son identifiant est conservé sur la période de paie après comptabilisation.

## Concurrence, isolation et permissions

Toutes les requêtes sont filtrées par `organization_id`. Les transitions sensibles verrouillent la période avec `SELECT ... FOR UPDATE`; les créations concurrentes s’appuient également sur les contraintes d’unicité et convertissent les collisions en `409 Conflict`. Les écritures de correction verrouillent le bulletin source et la période dans un ordre déterministe.

Les permissions prévues sont `payroll_employee:*`, `payroll_contract:*`, `payroll_rule_set:*`, `payroll_period:create`, `payroll_period:read`, `payroll_period:calculate`, `payroll_period:validate`, `payroll_period:lock`, `payroll_period:post`, `payroll_slip:read`, `payroll_correction:create` et `payroll_audit:read`. Les rôles administrateur et propriétaire disposent de toutes les opérations ; le rôle comptable reçoit les opérations Paie nécessaires à la validation et à la comptabilisation, tandis que les rôles lecture sont limités à la consultation.

## Plan de migration et de tests

La migration `0008_add_payroll_management` suivra `0007_add_treasury_bank_accounts`. Elle créera les tables dans l’ordre des dépendances, les index tenant-scopés et les contraintes de statuts, d’unicité et de montants, avec un `downgrade()` inverse complet.

Les tests couvriront les calculs unitaires (brut, cotisations, plafonds, barème, arrondis, net), les transitions, les corrections, la sécurité multi-tenant, le RBAC, les collisions concurrentes, la comptabilisation équilibrée et le rejet d’une période fiscale fermée. Une suite dédiée PostgreSQL utilisera `asyncpg` et un service PostgreSQL GitHub Actions afin de valider les contraintes et les verrous sur le moteur cible, en complément de la suite SQLite rapide.
