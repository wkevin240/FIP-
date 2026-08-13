# Notes réglementaires — Paie Cameroun (référence d’architecture)

**Consultées le 13 août 2026.** Ces informations servent à concevoir un moteur paramétrable et versionné. Elles ne constituent pas un conseil juridique ni une source à encoder directement comme règle métier immuable.

| Sujet | Constat utile pour le modèle | Source |
|---|---|---|
| CNPS | L’employeur calcule, déclare et reverse les parts patronale et salariale des cotisations sociales ; les branches sont fixées par décret. [1] | CNPS |
| Cotisation pension | La source de référence fiscale PwC, revue le 31 décembre 2025, présente une part salariale de 4,2 % plafonnée à 750 000 XAF mensuels. [2] | PwC |
| Cotisations employeur | La documentation CLEISS au 1er janvier 2024 détaille les branches familiales, pension et accidents du travail, avec plafonds et taux différenciés selon le régime et le risque. [3] | CLEISS |
| IRPP salarial | La DGI décrit une assiette annuelle, l’abattement de frais professionnels, la déduction des cotisations obligatoires, un abattement de 500 000 XAF, un barème progressif et une majoration CAC. Elle confirme la retenue à la source mensuelle opérée par l’employeur. [4] | DGI Cameroun |

## Conséquences de conception

1. Les taux, plafonds, abattements, tranches et directions (employeur/salarié) doivent être stockés comme **paramètres réglementaires datés**, propres à une organisation ou à un jeu de référence.
2. Les barèmes progressifs doivent être modélisés par tranches ordonnées, avec bornes et taux explicites ; aucune valeur ne doit être intégrée en dur au domaine de calcul.
3. Chaque résultat de paie doit conserver un instantané des paramètres appliqués, de la base, du taux, du plafond et du montant arrondi afin de permettre l’audit et la reproductibilité historique.
4. Toute activation d’un jeu de paramètres réglementaires pour une paie opérationnelle doit être validée par l’organisation et, avant mise en production, rapprochée des textes en vigueur ou de son conseil compétent.

## Références

[1]: https://www.cnps.cm/en/employeurs/obligations-de-lemployeur1.html "CNPS — Obligations de l’employeur"
[2]: https://taxsummaries.pwc.com/republic-of-cameroon/individual/other-taxes "PwC — Social security contributions"
[3]: https://www.cleiss.fr/docs/cotisations/cameroun.html "CLEISS — Cotisations au Cameroun"
[4]: https://impots.cm/fr/document/impot-sur-le-revenu-des-personnes-physiques-irpp-ce-que-vous-devez-savoir "DGI Cameroun — IRPP"
