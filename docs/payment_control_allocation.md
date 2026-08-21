# Payment Control / Allocation

## Modèle canonique

FIP conserve les modèles de paiement clients `payments` et fournisseurs `supplier_payments` déjà présents. Le lot ajoute `payment_allocations` et `supplier_payment_allocations` pour représenter les affectations explicites vers plusieurs factures sans créer un second moteur de paiement.

Chaque allocation est tenant-scopée et référencée par des FK composites `(organization_id, source_id)`. Son montant est `Numeric(18, 2)`, strictement positif. Une clé d’idempotence est obligatoire et unique par organisation.

## Invariants

Pour chaque paiement, le service verrouille le paiement et la facture avec `SELECT ... FOR UPDATE` avant de calculer les allocations existantes. Il refuse une allocation si :

- le montant est nul ou négatif ;
- le total alloué dépasserait le montant du paiement ;
- le total alloué dépasserait l’encours de la facture ;
- le paiement ou la facture appartient à une autre organisation.

Le montant non appliqué est calculé comme `payment amount - total allocated`, avec une quantification Decimal à deux décimales. Les états sont `UNAPPLIED`, `PARTIALLY_APPLIED` et `FULLY_APPLIED`.

## Intégration

Les allocations ne modifient pas directement une écriture `POSTED`, ne postent pas automatiquement dans Accounting et ne rapprochent pas automatiquement une transaction bancaire. Le contrôle Payment Control produit des états explicables. Liquidity Control réutilise les allocations explicites pour calculer les montants clients et fournisseurs non appliqués.

Un `invoice_id` historique n’est pas une allocation canonique : lorsqu’aucune ligne d’allocation n’existe, le montant alloué est zéro et le paiement est `UNAPPLIED`. Le système ne transforme donc jamais implicitement le lien facture en allocation à 100 %.

La comparaison Payment ↔ BankTransaction est read-only. Elle recherche, dans la même organisation et à la même date, une référence exacte dans `BankTransaction.reference` ou `BankTransaction.external_id`, puis compare le montant signé en Decimal. Une absence de référence, une absence de transaction, une correspondance multiple ou un écart de montant produit `NOT_READY` ou `INCOMPLETE` avec un blocker explicable ; aucune ligne n’est modifiée et aucun rapprochement automatique n’est créé.

## API

- `POST /invoicing/payment-control/customer/allocations`
- `POST /invoicing/payment-control/supplier/allocations`
- `GET /invoicing/payment-control/customer/{payment_id}/control`
- `GET /invoicing/payment-control/supplier/{payment_id}/control`
- `GET /invoicing/payment-control/reconciliation?as_of=YYYY-MM-DD`

Aucun endpoint ne déclenche un rapprochement bancaire automatique ni une comptabilisation implicite.
