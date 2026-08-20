# Working Capital

Le moteur Working Capital expose `GET /accounting/working-capital/calculate?period_start=YYYY-MM-DD&as_of_date=YYYY-MM-DD`. Les deux dates sont obligatoires et tous les agrégats respectent strictement cette fenêtre.

Le calcul agrège les factures clients réelles, les factures fournisseurs Procurement réelles et la valorisation courante des stocks existants. Il produit les soldes Accounts Receivable, Inventory, Accounts Payable et le besoin en fonds de roulement opérationnel `AR + Inventory - AP` en Decimal.

DSO est calculé comme `AR / ventes opérationnelles × 365` lorsque les factures clients de la période fournissent un dénominateur positif. DPO est calculé comme `AP / achats fournisseurs × 365` lorsque les factures fournisseurs fournissent un dénominateur positif. En l’absence de dénominateur positif, la métrique est `NOT_READY` et sa valeur reste nulle.

DIO et CCC ne sont pas présentés artificiellement. Le modèle actuel ne fournit pas encore de mapping organisationnel fiable entre les comptes du ledger et le COGS. DIO reste donc `NOT_READY`, et CCC reste `NOT_READY` avec l’explication explicite que la formule `DSO + DIO - DPO` ne peut pas être complète sans COGS réel. Aucun compte, mapping, stock ou transaction fictif n’est créé.
