# Import normalisé de relevés bancaires

L’import de relevé bancaire transforme un fichier CSV UTF-8 dans des transactions bancaires canoniques tenant-scopées. Il n’invente aucune transaction, contrepartie ou écriture comptable. Les transactions importées restent disponibles pour les flux existants de Trésorerie, de comptabilisation explicite et de rapprochement bancaire.

## Endpoint et autorisation

L’endpoint `POST /api/v1/treasury/transactions/imports/csv` accepte un fichier multipart `statement_file`, le champ `treasury_bank_account_id` et l’en-tête obligatoire `Idempotency-Key`. Il exige la permission `treasury_transaction:create`.

## Format CSV_V1

Le fichier doit être encodé en UTF-8 ou UTF-8 avec BOM. La première ligne doit être exactement la suivante, dans cet ordre :

```text
external_id,transaction_date,value_date,amount,description,reference
```

| Colonne | Règle |
|---|---|
| `external_id` | Identifiant externe non vide, unique dans le fichier, 100 caractères maximum. |
| `transaction_date` | Date ISO `YYYY-MM-DD` obligatoire. |
| `value_date` | Date ISO facultative ; vide si inconnue. |
| `amount` | Montant `Decimal` non nul, avec au plus deux décimales. Le signe détermine le sens bancaire. |
| `description` | Libellé non vide, 500 caractères maximum. |
| `reference` | Référence facultative, 100 caractères maximum. |

Le fichier est plafonné à 5 MiB et 10 000 lignes. Toute colonne manquante, colonne supplémentaire, ligne mal formée, montant invalide ou doublon interne entraîne un rejet `422` sans création partielle.

## Idempotence, doublons et concurrence

Le contenu brut est haché SHA-256. Une répétition de la même clé d’idempotence, du même compte bancaire, du même nom de fichier et du même contenu retourne le lot existant sans recréer de transaction ni d’événement Audit. Toute réutilisation divergente de la clé est rejetée `409`.

Une transaction déjà connue pour le même compte comptable bancaire et le même `external_id` est enregistrée comme ligne `DUPLICATE` dans le nouveau lot, sans être recréée. Sinon, elle est créée comme transaction canonique et sa ligne est `IMPORTED`.

Les verrous transactionnels PostgreSQL sur la clé d’idempotence et les identifiants externes sérialisent les imports concurrents. Ils empêchent la création de deux transactions pour un même mouvement source tout en permettant une traçabilité complète des lignes détectées comme doublons.

## Intégrité, Audit et sécurité

La migration `0021_bank_statement_imports` crée les tables `bank_statement_imports` et `bank_statement_import_lines`. Elles disposent de FK composites incluant `organization_id`, de contraintes de comptage et de liens vers les transactions canoniques. Les tables sont détenues par `fip_accounting_owner`, avec les seuls droits `SELECT` et `INSERT` pour `fip_user`.

La création du lot, de ses lignes, des transactions nouvelles et de l’événement `BANK_STATEMENT_IMPORTED` est atomique. En cas de rejet ou d’échec, la transaction entière est annulée : aucune transaction importée, aucune ligne de lot et aucun Audit de succès ne subsistent.
