# FP&A Scenarios

Le moteur de scénarios est une couche de pilotage au-dessus du ledger central. Un scénario est toujours rattaché à une organisation et à un exercice fiscal existant. Ses hypothèses sont explicites, saisies par l’organisation, rattachées à une période, un compte et éventuellement une valeur analytique existants, et stockées en `Decimal(18,2)`.

Un scénario `DRAFT` n’est pas exploitable pour une prévision. Il doit comporter au moins une hypothèse et être `APPROVED` ou `LOCKED`; sinon l’API expose `ready=false`. Le moteur ne crée aucune donnée de démonstration, ne modifie jamais les écritures `POSTED` et ne comptabilise aucune hypothèse. Les futures prévisions consommeront uniquement les scénarios approuvés, les budgets approuvés et les actuals issus des écritures `POSTED`.

Les opérations de création, d’ajout d’hypothèse et d’approbation sont tenant-scopées, protégées par RBAC, auditées dans la même transaction et verrouillent le scénario lors des transitions sensibles. Les contraintes PostgreSQL empêchent les références inter-organisation et les doublons, y compris lorsqu’une hypothèse n’a pas de dimension analytique.

Endpoints : `POST /accounting/scenarios`, `POST /accounting/scenarios/{id}/assumptions`, `POST /accounting/scenarios/{id}/approve` et `GET /accounting/scenarios/{id}/status`.
