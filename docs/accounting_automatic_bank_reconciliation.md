# Rapprochement bancaire automatique prudent

## Finalité

Le rapprochement automatique s’appuie exclusivement sur les transactions bancaires et les écritures `POSTED` déjà présentes dans l’organisation active. Il ne crée ni transaction bancaire, ni écriture comptable, ni compte, ni donnée de démonstration.

## Critères d’éligibilité

Une correspondance n’est automatiquement appliquée que si elle est unique et déterministe : même compte bancaire, même organisation, montant strictement égal en `Decimal`, même sens débit/crédit et date dans la fenêtre configurée de zéro à quatre-vingt-dix jours.

| Statut | Signification | Effet |
|---|---|---|
| `AUTO_ELIGIBLE` | Une unique correspondance exacte est disponible | Peut être rapprochée par l’opération d’application. |
| `UNMATCHED` | Aucune écriture exacte ne correspond | Aucune écriture ni rapprochement n’est créé. |
| `AMBIGUOUS` | Plusieurs écritures correspondent, ou une même écriture serait proposée à plusieurs transactions | Aucune application automatique. |
| `SKIPPED_CONCURRENTLY` | Le candidat a changé entre aperçu et application | Aucune seconde correspondance ; l’utilisateur peut relancer l’aperçu. |

## API et permissions

| Route | Permission | Effet |
|---|---|---|
| `POST /api/v1/accounting/bank-reconciliation/automatic/preview` | `bank_reconciliation:read` | Produit les suggestions sans modifier les données. |
| `POST /api/v1/accounting/bank-reconciliation/automatic/apply` | `bank_reconciliation:match` | Applique uniquement les suggestions `AUTO_ELIGIBLE`. |

Les rapprochements appliqués portent le mode `AUTO_EXACT`; les rapprochements manuels conservent le mode `MANUAL`. Les deux créent l’événement append-only `BANK_TRANSACTION_RECONCILED` dans la même transaction que le rapprochement.

## Limites assumées

Ce lot ne devine pas les rapprochements partiels, groupés, ni les correspondances approximatives de libellé. Ces cas restent visibles comme non rapprochés ou ambigus, afin d’éviter tout effet comptable automatique injustifié.
