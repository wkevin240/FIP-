# Financial Closing Readiness

L’endpoint `GET /accounting/closing-readiness/{fiscal_year_id}` évalue la préparation d’un exercice sans modifier la base. Il retourne `READY` uniquement lorsque les contrôles déterministes sont satisfaits ; sinon il retourne `NOT_READY` avec la liste complète des blockers.

Les contrôles couvrent l’existence des périodes de l’exercice, l’absence de périodes `OPEN` ou `LOCKED`, l’absence d’écritures `DRAFT`, l’absence d’exceptions bancaires non `RECONCILED`, la clôture de tous les relevés importés, l’existence d’un enregistrement `PeriodClosing` pour chaque période et l’équilibre mathématique des mouvements `POSTED` (`total_debit = total_credit`).

Tous les compteurs sont tenant-scopés par `organization_id` et les totaux restent en Decimal. Aucun exercice, période, écriture, exception bancaire ou clôture fictive n’est créé. En l’absence de données réelles, FIP retourne les compteurs à zéro et `NOT_READY` avec les blockers correspondant à la configuration absente.
