# Avoirs et règlements Facturation → Accounting

Ce lot relie les avoirs et règlements existants de Facturation au moteur sécurisé `JournalEntryService`. Aucun moteur comptable parallèle n’est introduit et aucune écriture `POSTED` n’est modifiée directement.

Un avoir porte une ventilation explicite `HT + TVA = TTC`, contrôlée par le contrat applicatif et une contrainte PostgreSQL. Sa comptabilisation débite les comptes produits et TVA du profil comptable Facturation, puis crédite la créance client. Un règlement débite un compte bancaire ou caisse explicitement fourni par l’organisation puis crédite la créance client.

Les liaisons de source vers les écritures comptables sont uniques, tenant-scopées, idempotentes et auditées dans la même transaction. Les comptes, journaux et périodes doivent exister réellement dans l’organisation ; FIP ne crée aucun compte, journal, facture, avoir ou règlement artificiel.
