# FP&A KPI Engine

Le moteur KPI lit exclusivement les écritures `POSTED` de l’organisation et, si demandé, d’une période fiscale existante. Les mouvements sont agrégés par `account_type` réel : produits, charges et résultat net comptable sont calculés en `Decimal(18,2)`, puis la marge nette est calculée uniquement si un produit non nul existe.

Les KPI qui nécessitent une granularité absente du modèle actuel ne sont pas approximés. `EBITDA` et `GROSS_MARGIN` restent `NOT_READY` tant qu’un mapping organisationnel distingue les coûts des ventes et les charges opérationnelles. `DSO` et `DPO` restent `NOT_READY` tant que les créances clients, dettes fournisseurs, ventes et achats ne sont pas configurés dans un référentiel exploitable. L’API expose la raison explicite et ne fabrique aucun chiffre.

Les écritures `DRAFT` et `VOIDED` sont exclues. Le moteur ne crée aucune écriture ni donnée persistante et ne contourne ni le ledger ni les modules Facturation/Procurement. Endpoint : `GET /accounting/kpis?fiscal_period_id=<id>` avec permission `kpi:read`.
