# Notes SYSCOHADA — Immobilisations et amortissements

**Consultées le 13 août 2026.** Ces notes encadrent la conception du module et ne constituent ni un paramétrage réglementaire automatique ni un conseil juridique.

| Principe de conception | Conséquence dans FIP | Référence |
|---|---|---|
| Le montant amortissable correspond au coût d’entrée diminué de la valeur résiduelle prévisionnelle. [1] | Chaque actif et composant doit conserver son coût d’origine, sa valeur résiduelle et son montant amortissable à l’instant de création du plan. | Plan comptable OHADA |
| La dotation est répartie sur la durée d’utilité au moyen d’un plan prédéfini ; les méthodes peuvent être linéaire, dégressive ou unités de production. [1] | Le moteur doit accepter des méthodes configurables, avec leurs paramètres et un échéancier immuable généré en `Decimal`. | Plan comptable OHADA |
| L’amortissement débute lorsque le bien est en état et en lieu d’utilisation prévus. [1] | La mise en service est une transition distincte de l’acquisition ; aucun plan ne peut commencer avant sa date. | Plan comptable OHADA |
| Les révisions de perspectives d’utilisation exigent une information quantifiée, et les dotations doivent être pratiquées à chaque clôture. [1] | Toute révision doit créer une nouvelle version de plan et un événement d’audit ; les périodes déjà comptabilisées restent immuables. | Plan comptable OHADA |
| Le compte d’amortissement est crédité par le débit d’un compte de dotation ; lors d’une cession, les amortissements du bien cédé sont annulés. [1] | Les profils comptables d’immobilisation doivent fournir les comptes de coût, amortissement cumulé, dotation, produit de cession et sortie, puis déléguer les écritures équilibrées à Accounting. | Plan comptable OHADA |

## Conséquences d’architecture

1. Les durées, méthodes, taux éventuels, unités prévues et conventions de prorata doivent être des données versionnées par catégorie ou actif ; elles ne sont jamais intégrées en dur au moteur.
2. Les calculs doivent être déterministes : même instantané de plan, mêmes données d’entrée et même date de clôture produisent le même échéancier, les mêmes montants cumulés et la même valeur nette comptable.
3. Les composants amortissables sont des unités de calcul indépendantes, reliées à une immobilisation mère, afin de préserver leurs coûts, durées et échéanciers propres.
4. Une cession ou sortie ne peut modifier un plan déjà comptabilisé. Elle doit conserver le coût, l’amortissement cumulé, la valeur nette comptable, le produit éventuel et les écritures produites.

## Références

[1]: https://plan-comptable-ohada.com/nouvelle-norme-2016/compte/28.html "Plan comptable OHADA — Compte 28 : Amortissements"
