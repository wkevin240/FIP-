# Intégration Trésorerie → Accounting

Les transactions de relevé bancaire restent importées dans Trésorerie. Leur comptabilisation est ensuite une opération explicite, tenant-scopée et auditable : l’organisation configure un journal comptable réel, puis fournit la contrepartie réelle de chaque transaction. FIP ne déduit ni ne crée jamais cette contrepartie.

Pour un montant bancaire positif, l’écriture débite le compte bancaire `ASSET` et crédite la contrepartie. Pour un montant négatif, elle débite la contrepartie et crédite le compte bancaire. Le montant absolu est conservé en `Decimal(18,2)`. Une période fiscale ouverte est requise et l’écriture est créée puis comptabilisée exclusivement via `JournalEntryService`.

La table `treasury_accounting_postings` rend la liaison transaction bancaire → écriture unique. Les clés étrangères composites imposent la même organisation pour la transaction source, la contrepartie et l’écriture. La création de l’écriture, de la liaison et de l’événement Audit `TREASURY_TRANSACTION_POSTED_TO_ACCOUNTING` est atomique. Un nouvel appel sur une transaction déjà comptabilisée renvoie la liaison existante sans double effet.

Le rapprochement bancaire existant reste séparé : il rapproche une transaction de relevé avec une écriture `POSTED`. La comptabilisation de trésorerie crée précisément l’écriture qui peut être utilisée par ce contrôle, sans modifier les règles de rapprochement.
