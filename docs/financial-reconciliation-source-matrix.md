# Matrice des sources — Financial Reconciliation & Operating Metrics

| KPI | Source réelle existante | Service réutilisé | Formule retenue | Données manquantes / limite | Statut cible |
|---|---|---|---|---|---|
| AR Outstanding | `Invoice`, `PaymentAllocation`, `CreditNote` | `ReceivableService` / allocations canoniques | `invoice total - canonical payment allocations - issued credits` | Aucun crédit ne doit être déduit sans avoir réel et daté | READY si factures et sources existent |
| AP Outstanding | `PurchaseInvoice`, `SupplierPaymentAllocation` | `PaymentControlService` / Procurement | `purchase invoice total - canonical supplier allocations` | Aucun service AP statement dédié ; calcul limité aux allocations persistées | READY si factures validées et sources existent |
| DSO | AR as-of + `REVENUE` du `FinancialCalculationService` | `FinancialCalculationService` | `average AR / credit revenue × days` | Revenue doit être mappé, POSTED et non nul | READY sinon NOT_READY |
| DPO | AP as-of + factures fournisseurs validées | Procurement / allocations | `average AP / validated supplier invoice total × days` | Le modèle ne fournit pas une définition distincte des achats ; le total des factures validées est utilisé explicitement | READY sinon NOT_READY |
| Working Capital | AR, AP, `StockBalance` | `KPIService` + Inventory source | `AR + Inventory - AP` | `StockBalance` est un snapshot courant ; pas de valeur historique fiable avant la date courante | READY pour snapshot courant complet, sinon NOT_READY |
| Liquidity | `LiquidityControlService` | `LiquidityControlService.control` | `Cash + AR - AP` selon le service source | La liquidité reste INCOMPLETE si Treasury/Bank/Cash Forecast/Reconciliation ne sont pas READY | READY si service source READY |
| Cash Coverage | Aucune définition métier explicite trouvée | Aucun | Aucune formule inventée | Définition non configurée | NOT_READY |
| Bank ↔ Payment | Transactions et rapprochement existants | `AccountingTreasuryReconciliationService` / `PaymentControlService` | Contrôles date, référence, montant, posting POSTED | Une métrique agrégée KPI n’expose pas encore tous les détails de rapprochement | INCOMPLETE si écarts |

Les résultats sont tenant-scopés par `organization_id`, filtrés par date et calculés en `Decimal`. Aucune donnée fictive n’est ajoutée hors fixtures de test et aucune écriture comptable n’est créée par ces calculs.
