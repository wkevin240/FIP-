# Accounts Payable

Le lot Accounts Payable ajoute une vue opérationnelle de la dette fournisseur au-dessus du module Procurement existant. Il ne recrée ni les fournisseurs, ni les factures, ni les paiements, ni le posting Accounting déjà en place.

Le relevé `GET /procurement/payables/statement?as_of_date=YYYY-MM-DD` agrège uniquement les factures fournisseurs réelles dans les statuts `VALIDATED`, `PARTIALLY_PAID` et `PAID`. Pour chaque fournisseur, FIP expose le montant facturé, le montant payé, le solde restant, la tranche d’âge et le montant en retard. Les montants sont calculés en Decimal à partir de `total_amount - paid_amount`; aucun montant ne peut devenir négatif dans le résultat.

L’ageing utilise exclusivement la date d’échéance réelle et la date de reporting demandée : `CURRENT`, `1-30`, `31-60`, `61-90` ou `90+`. Une échéance absente ne reçoit pas de date inventée et reste `CURRENT` avec un overdue nul. Le filtre `supplier_id` est vérifié dans l’organisation courante avant tout calcul.

Le périmètre de ce premier incrément est volontairement en lecture et réconciliation. Les échéanciers de paiement fournisseur multi-factures et les règlements non appliqués feront l’objet d’un incrément séparé, car le modèle actuel de `SupplierPayment` reste explicitement rattaché à une facture unique.
