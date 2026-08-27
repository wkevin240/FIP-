# Audit produit FIP — 21 août 2026

## État vérifié

`origin/main` est au commit `0a17a73977c3e3c4b1a6d06dd6889ab15764bac0` (merge PR #48). Les PR ouvertes vérifiées sont #39 à #46, #49, #50 et #51. Les PR #49 à #51 sont ouvertes et mergeables ; #51 est empilée sur #50, elle-même empilée sur #49. Aucune PR n’est fusionnée pendant cet audit.

La tête Alembic de `main` est `0027_fpa_scenarios`. Les révisions `0028_treasury_liquidity_alerts` et `0029_payment_allocations` existent dans les branches ouvertes #50/#51 et ne sont pas dans `main`.

## Capacités réellement présentes

Accounting fournit le ledger central, les écritures équilibrées, les périodes, la clôture, les contre-passations/corrections, les protections PostgreSQL, les états financiers, la liasse SYSCOHADA, le tableau de flux, la TVA et l’audit. Treasury fournit les comptes bancaires, transactions, imports OFX/MT940, règles bancaires, rapprochement, position de liquidité, cash forecast et Banking Control Center selon les branches concernées. AR fournit factures, avoirs, règlements, allocations, ageing et snapshot de recouvrement. AP/Procurement fournit fournisseurs, factures fournisseurs, paiements, posting Accounting, ageing et allocations avancées selon les PR ouvertes. Payroll, Inventory, Fixed Assets et FP&A possèdent également des services réels et des intégrations Accounting partielles ou établies.

## Ruptures O2C

Le dépôt ne possède pas de référentiel client dédié, de prospect, de devis, de commande client, de livraison ou de lien livraison-facture. La facture utilise principalement des informations client embarquées. Le workflow réel commence donc à la facture et ne couvre pas le cycle commercial amont ; la livraison et la reconnaissance opérationnelle du revenu restent hors FIP.

Le recouvrement existe sous forme de snapshot d’encours et d’ageing, mais le workflow de relance, promesse de paiement, escalade et historique de contact n’est pas présent. La réconciliation Payment ↔ BankTransaction est traitée dans la PR #51, non fusionnée.

## Ruptures P2P

Le dépôt possède fournisseur, facture fournisseur `DRAFT → VALIDATED`, paiements, allocations et posting. En revanche, aucune demande d’achat, commande fournisseur, réception, rapprochement commande-réception-facture, circuit d’approbation, rejet ou séparation des tâches n’a été trouvé. L’utilisateur doit encore gérer hors FIP l’autorisation de dépense et la preuve de réception avant validation.

## Ruptures Treasury et clôture

Les imports, transactions, rapprochements, contrôles bancaires et forecasts existent. La complétude et les exceptions sont exposées par plusieurs vues, mais le workflow de clôture bancaire opérationnelle, avec sign-off, responsabilité, pièces justificatives et verrou de période intégré, reste incomplet. Les branches #49/#50/#51 portent des incréments encore non fusionnés.

## Ruptures contrôle interne et documents

Audit et RBAC existent. Le dépôt ne montre pas de système documentaire transversal reliant pièces justificatives, factures, paiements, commandes, réceptions, écritures et relevés. Les exceptions existent par domaine mais ne sont pas réunies dans un workflow de contrôle interne avec ownership, résolution, échéance et sign-off.

## Priorisation

### P0

**P0-1 — Gouvernance des fusions et intégration des PR ouvertes.** Les capacités Treasury/AR/AP récentes ne sont pas disponibles dans `main` ; l’écart est organisationnel et bloque la cohérence de la version exploitable.

**P0-2 — Chaîne P2P contrôlée avant posting.** L’absence d’approbation et de preuve de réception permet à une facture fournisseur validée d’atteindre le posting sans contrôle de dépense. Dépendances : Procurement, Audit, RBAC, périodes et Accounting existants.

### P1

**P1-1 — Référentiel et cycle commercial O2C amont.** Clients, devis, commandes et livraisons manquent avant facturation. Dépendances : Facturation, AR, Inventory et Accounting.

**P1-2 — Workflow de relance AR.** Le snapshot d’ageing existe, mais pas les actions, promesses, tâches, escalades et résultats.

**P1-3 — Rapprochement commande-réception-facture P2P.** Nécessaire pour un contrôle de facture professionnel.

**P1-4 — Clôture Treasury signée et dossier de clôture.** Les contrôles existent mais il manque l’orchestration opérationnelle, le sign-off et les pièces justificatives.

**P1-5 — Gestion documentaire transversale.** Nécessaire pour audit, contrôle fiscal et exploitation quotidienne.

**P1-6 — Centre d’exceptions transversal.** Les blockers des domaines doivent devenir des exceptions assignables, suivies et résolues.

### P2/P3

Les améliorations UI, dashboards décoratifs, optimisation de performance, notifications et confort utilisateur viennent après la fermeture des ruptures P0/P1.

## Décision d’implémentation

Le premier lot construit après l’audit est **P2P Procurement Approval Workflow**, car il réutilise directement le modèle et le service Procurement existants, protège le posting Accounting sans créer de moteur parallèle et traite une rupture de contrôle P0. Le lot doit ajouter états, approbation/rejet, séparation des tâches, idempotence, concurrence, audit, RBAC et règles tenant-scopées sans seuil métier par défaut ni données fictives.
