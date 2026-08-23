# Financial Closing Control Service

Le `FinancialClosingControlService` est une couche d’orchestration read-only. Il ne remplace ni `ClosingService`, ni `ClosingReadinessService`, ni `KPIService`, ni les contrôles Treasury/Reporting existants.

## Contrat

L’endpoint `GET /api/v1/accounting/closing-control/{fiscal_year_id}/periods/{fiscal_period_id}` évalue une période pour une organisation tenant-scopée. La réponse contient `organization_id`, l’exercice, la période, ses dates, le statut global, tous les contrôles et tous les blockers structurés.

Chaque contrôle expose son code, son statut, sa formule lorsque pertinente, ses valeurs `actual` et `expected`, sa différence Decimal, ses identifiants sources et ses blockers. Chaque blocker contient un code, un module, une sévérité, une description, les identifiants sources disponibles et un montant Decimal lorsqu’il est pertinent.

## Sources réutilisées

Le contrôle `CLOSING_READINESS` consomme `ClosingReadinessService` pour les contrôles d’exercice, de périodes, de brouillons, de clôtures de périodes, d’exceptions bancaires et d’équilibre POSTED. Le contrôle `FISCAL_PERIOD` vérifie la période demandée et son appartenance simultanée à l’organisation et à l’exercice.

Les contrôles AR, AP, DSO, DPO, Working Capital, Net Working Capital, Liquidity et Reconciliation consomment les sorties du `KPIService`. Le KPI Service reste l’unique source de calcul des montants et ratios concernés.

Le contrôle `REPORTING_TRIAL_BALANCE` consomme `ReportingService.trial_balance` sur les dates exactes de la période. Il retourne `NOT_READY` sans lignes POSTED et `INCOMPLETE` lorsqu’un déséquilibre est signalé.

## Statuts

`READY` signifie que tous les contrôles exécutés sont satisfaits. `NOT_READY` signifie qu’une source obligatoire, une configuration ou un état de période empêche la conclusion. `INCOMPLETE` signifie qu’une incohérence, un écart ou une source contradictoire est détecté. Les blockers sont tous conservés dans un ordre déterministe ; le service ne s’arrête pas au premier problème.

## Historique et sécurité

Le service borne KPI et reporting aux dates de la période. Il ne modifie aucune écriture, ligne, facture, paiement, transaction bancaire, budget ou forecast. La résolution de période exige `organization_id`, `fiscal_year_id` et `fiscal_period_id` cohérents, empêchant l’accès à une période d’un autre tenant.

Aucune migration, configuration financière par défaut, seed ou donnée de démonstration n’est nécessaire ou ajoutée par ce lot.
