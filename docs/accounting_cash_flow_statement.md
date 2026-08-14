# Tableau de flux de trésorerie comptable

## Finalité du lot

Ce lot complète les états professionnels par un tableau de flux de trésorerie construit directement à partir des écritures comptables reconnues par le moteur Accounting : les écritures `POSTED` et les originaux `VOIDED` nécessaires à la neutralisation correcte de leurs contre-passations. Il exploite les comptes de trésorerie et les contreparties configurées dans l’organisation, sans modifier le domaine Trésorerie ni importer de relevés externes.

La configuration est tenant-scopée et explicite : un compte actif peut être défini comme compte de trésorerie, ou comme contrepartie classée `OPERATING`, `INVESTING` ou `FINANCING`. Un compte de trésorerie doit être de type `ASSET`. Les comptes non configurés ne sont jamais classés silencieusement.

## Calcul direct et réconciliation

Pour chaque écriture `POSTED` comprise dans l’intervalle demandé, le moteur calcule le mouvement net des seuls comptes configurés comme trésorerie : `débit − crédit`. Le mouvement est classé lorsque toutes les contreparties non-trésorerie appartiennent à une unique catégorie. Une écriture comportant une contrepartie non configurée ou plusieurs catégories devient `UNCLASSIFIED` et rend l’état incomplet, sans interrompre la réconciliation arithmétique.

| Élément | Formule / règle |
|---|---|
| Trésorerie d’ouverture | Somme des mouvements des comptes de trésorerie `POSTED` jusqu’à la veille de `start_date` |
| Flux d’exploitation | Mouvements de trésorerie dont toutes les contreparties sont `OPERATING` |
| Flux d’investissement | Mouvements de trésorerie dont toutes les contreparties sont `INVESTING` |
| Flux de financement | Mouvements de trésorerie dont toutes les contreparties sont `FINANCING` |
| Flux non classés | Mouvements comportant une contrepartie inconnue ou ambiguë |
| Trésorerie de clôture calculée | Ouverture + flux d’exploitation + investissement + financement + non classés |
| Réconciliation | Clôture calculée = solde comptable des comptes de trésorerie à `end_date` |

Les calculs utilisent exclusivement `Decimal`. Les brouillons `DRAFT` sont exclus. Lorsqu’une écriture est annulée, l’original `VOIDED` et sa contre-passation `POSTED` sont tous deux pris en compte afin de préserver le mouvement historique net et d’éviter un faux flux inverse. L’état retourne les numéros des écritures non classifiées ; `is_complete` vaut `false` tant qu’une configuration empêche une classification unique. Ainsi, un état peut être mathématiquement réconcilié tout en indiquant honnêtement qu’il reste à classer.

## API et permissions

| Opération | Route | Permission |
|---|---|---|
| Créer une configuration de compte | `POST /api/v1/accounting/cash-flow/mappings` | `cash_flow:configure` |
| Lister la configuration active | `GET /api/v1/accounting/cash-flow/mappings` | `cash_flow:read` |
| Produire le tableau de flux | `GET /api/v1/accounting/cash-flow/statement?start_date=...&end_date=...` | `cash_flow:read` |

Chaque création de mapping génère l’événement Audit `CASH_FLOW_ACCOUNT_MAPPING_CREATED` dans la même transaction. La migration `0014_cash_flow_statement` applique une clé étrangère composite `(organization_id, account_id)`, attribue la table à `fip_accounting_owner`, révoque les droits publics et accorde les privilèges de configuration minimaux à `fip_user`.

## Limites explicites

L’incrément livre une méthode directe à partir des comptes configurés. Il ne traite pas encore les ajustements non monétaires de la méthode indirecte, les rapprochements bancaires incomplets comme source de flux, les prévisions de trésorerie, les conversions multi-devises, les états consolidés ni les formats de liasse nationaux. Ces extensions resteront des lots séparés, testés et tenant-scopés.
