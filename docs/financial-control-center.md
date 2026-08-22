# Financial Control Center

Le Financial Control Center est une vue consolidée et non mutative de l’état de contrôle financier d’une organisation. Il vérifie les écritures `DRAFT`, les périodes ouvertes à la date de contrôle, les exceptions bancaires non résolues, les transactions bancaires non rapprochées et l’équilibre des mouvements `POSTED`.

Le résultat est `READY` uniquement lorsque tous les blockers sont absents et que le total débit POSTED est égal au total crédit POSTED. Sinon, le statut `NOT_READY` est retourné avec des codes déterministes : `DRAFT_JOURNAL_ENTRIES`, `OPEN_CURRENT_PERIOD`, `UNRESOLVED_BANKING_EXCEPTIONS`, `UNRECONCILED_BANK_TRANSACTIONS` ou `POSTED_LEDGER_OUT_OF_BALANCE`.

La route ne clôture aucune période, ne résout aucune exception, ne rapproche aucune transaction et ne modifie aucune écriture. Elle est tenant-scopée, RBAC-protégée et utilise exclusivement Decimal pour les totaux comptables.
