# Conception — Module Immobilisations

## Objectif et périmètre

Le module gère les catégories, le registre des actifs, l’acquisition, la mise en service, les composants amortissables, les plans et échéanciers d’amortissement, les dotations comptabilisées, les cessions/sorties et l’historique append-only. Il réutilise le moteur Accounting pour toute écriture : aucune ligne comptable ne sera écrite directement depuis le domaine Immobilisations.

> **Principe directeur.** Une configuration de catégorie peut évoluer, mais une version de plan validée reste un instantané immuable : mêmes données, même date de calcul et même convention produisent le même échéancier et les mêmes montants.

## Agrégats et relations

| Agrégat | Données principales | Invariants |
|---|---|---|
| `FixedAssetCategory` | Code, nom, méthode par défaut, durée d’utilité, valeur résiduelle, profil comptable. | Unicité du code par organisation ; paramètres positifs et datés par création de plan. |
| `FixedAssetAccountingProfile` | Journal, compte d’immobilisation, amortissement cumulé, charge de dotation, contrepartie d’acquisition, produit de cession, perte de sortie. | Tous les comptes et le journal sont actifs et dans la même organisation. |
| `FixedAsset` | Code, catégorie, coût d’entrée, dates d’acquisition et de mise en service, état. | Coût ≥ valeur résiduelle ; mise en service non antérieure à l’acquisition ; aucune suppression après acquisition. |
| `FixedAssetComponent` | Coût, valeur résiduelle, durée, méthode, taux éventuel et état. | Coût total des composants ≤ coût de l’actif ; chaque composant génère son propre plan. |
| `DepreciationPlan` | Version, instantané des paramètres, date de début, date de fin, base amortissable, statut. | Un plan actif par composant ; versions déjà comptabilisées immuables. |
| `DepreciationScheduleLine` | Échéance, base, charge, cumul, VNC, statut, période fiscale et écriture. | Montants non négatifs ; cumul ≤ base amortissable ; une écriture par ligne ; ordre unique dans le plan. |
| `FixedAssetDisposal` | Date, type, produit, coût, amortissement cumulé, VNC, gain/perte, écriture. | Actif en service uniquement ; une seule sortie finalisée ; coût, cumul et VNC figés. |
| `FixedAssetAuditEvent` | Organisation, acteur, action, ressource, valeurs avant/après, motif, date. | Append-only, tenant-scopé, aucune route de suppression ou modification. |

## Méthodes et exactitude de calcul

| Méthode | Base | Formule périodique | Paramètres requis |
|---|---|---|---|
| `STRAIGHT_LINE` | Coût − valeur résiduelle | Base amortissable × fraction de période / durée totale | Durée en mois et convention mensuelle. |
| `DECLINING_BALANCE` | Valeur nette comptable d’ouverture | VNC d’ouverture × taux annuel × fraction de période | Taux annuel et durée de contrôle ; le dernier montant est ajusté sans dépasser la valeur résiduelle. |

Les montants sont convertis en `Decimal`, calculés sans `float`, puis arrondis au centime selon `ROUND_HALF_UP`. L’échéancier est mensuel. La convention `MONTHLY_PRORATA_DIE` utilise les jours calendaires réellement disponibles lors du premier mois ; le dernier montant est l’ajustement déterministe `base amortissable − cumul antérieur`, ce qui garantit que la valeur résiduelle est atteinte exactement, sans dépasser le coût ni produire une valeur nette comptable négative.

## Cycle de vie et intégration Accounting

| Transition | Préconditions | Effet |
|---|---|---|
| `DRAFT → ACQUIRED` | Catégorie et profil actifs ; comptes disponibles ; date et coût cohérents. | Écriture d’acquisition équilibrée, historisation et immutabilité du coût. |
| `ACQUIRED → IN_SERVICE` | Date de mise en service valide ; composants cohérents. | Création et figement des plans et échéanciers. |
| Échéance `PLANNED → POSTED` | Actif en service, période fiscale ouverte, ligne échue, plan actif. | Dotation équilibrée débit charge / crédit amortissement cumulé, puis verrouillage de la ligne. |
| `IN_SERVICE → DISPOSED` | Date de sortie cohérente ; toutes les dotations antérieures comptabilisées. | Gel des montants, calcul du résultat de cession, écriture équilibrée et blocage des nouvelles dotations. |

Les opérations de dotation et de sortie acquièrent un verrou de ligne sur l’actif, le composant, l’échéance et la période fiscale. Chaque écriture est ensuite créée et comptabilisée exclusivement par `JournalEntryService`.

## Données, sécurité et validation

Chaque requête lit et écrit exclusivement dans l’`organization_id` actif. Les permissions distinguent catégories, actifs, amortissements, cessions, consultation d’historique et audit. Les contraintes SQL complètent les règles de service : dates, montants, statuts, unicité tenant-scopée et références comptables restrictives.

La validation comprend des tests de calcul unitaires, des tests de service avec écritures Accounting réelles, des rejets de période close et de double comptabilisation, des tests de tenant isolation, une vérification PostgreSQL de migration/contraintes et l’exécution CI sur PostgreSQL.
