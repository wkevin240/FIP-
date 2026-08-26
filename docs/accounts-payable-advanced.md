# Accounts Payable avancé

Ce lot étend l’infrastructure `SupplierPayment` existante sans créer de moteur de paiement parallèle. `invoice_id` peut être nul à la création : le paiement est alors `UNAPPLIED` et ne modifie aucune facture fournisseur.

Une allocation explicite relie un paiement à une facture du même tenant et du même fournisseur. Une même somme peut être répartie sur plusieurs factures, avec des allocations partielles. Les contraintes PostgreSQL imposent les FK composites `organization_id + payment_id`, `organization_id + invoice_id` et `organization_id + supplier_id`, l’unicité de la paire paiement/facture et l’unicité de la clé d’idempotence.

Chaque allocation verrouille le paiement et la facture concernés. Le service refuse une allocation supérieure au montant non appliqué du paiement ou au solde de la facture. Un paiement déjà posté dans Accounting ne peut pas être réalloué. Le posting fournisseur existant est conservé mais refuse désormais tout paiement dont le montant n’est pas entièrement alloué.

Les opérations d’allocation et de déallocation produisent des événements Audit dans la transaction métier. La réconciliation retourne `UNAPPLIED`, `PARTIALLY_ALLOCATED` ou `FULLY_ALLOCATED`, sans inventer de match Treasury. La réconciliation AP/Treasury détaillée fera l’objet d’un incrément séparé après stabilisation de ces allocations.
