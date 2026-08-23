# Accounts Receivable

Le lot Accounts Receivable complète la facturation existante sans recréer le domaine Invoicing. Un paiement peut être reçu sans facture (`invoice_id=null`) et reste alors non appliqué. Une allocation explicite relie un paiement à une facture existante, verrouille les deux lignes, vérifie le montant disponible du paiement et le solde restant de la facture, puis met à jour le cycle de règlement de la facture en `PARTIALLY_PAID` ou `PAID`.

Chaque allocation est tenant-scopée et idempotente par `organization_id + idempotency_key`. Les paiements historiques rattachés à une facture sont repris par la migration 0028 comme allocations réelles ; aucune donnée fictive n’est créée. Une allocation produit un événement Audit dans la même transaction. Un paiement sans allocation ne peut pas être posté vers Accounting.

Le relevé `GET /invoicing/receivables/statement?as_of_date=YYYY-MM-DD` calcule les soldes à la date demandée, groupe les factures par identifiant client réel (`customer_tax_id`, sinon nom normalisé), et expose les tranches `CURRENT`, `1-30`, `31-60`, `61-90`, `90+`. Les montants en retard utilisent exclusivement `due_date` et `as_of_date`; une échéance absente reste `CURRENT` avec une raison implicite dans la donnée source, sans date métier inventée.

L’allocation est disponible via `POST /invoicing/payments/{payment_id}/allocations`. Le posting comptable existant reste le seul moteur Accounting et refuse explicitement tout paiement non appliqué.
