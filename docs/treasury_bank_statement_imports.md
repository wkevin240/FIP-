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

## Import OFX v2 XML

L’endpoint `POST /api/v1/treasury/transactions/imports/ofx` utilise le même multipart, le même `treasury_bank_account_id`, le même en-tête `Idempotency-Key` et la même permission que l’import CSV. Il prend en charge **OFX v2 XML uniquement** ; les fichiers OFX 1.x SGML sont explicitement rejetés car ils ne constituent pas du XML strictement vérifiable.

| Champ OFX | Destination normalisée | Règle |
|---|---|---|
| `BANKACCTFROM/ACCTID` | Compte bancaire de Trésorerie | Doit correspondre au numéro de compte configuré, après suppression des espaces. |
| `STMTTRN/FITID` | `external_id` | Obligatoire, unique dans le fichier et utilisé pour la déduplication. |
| `STMTTRN/DTPOSTED` | `transaction_date` | Obligatoire ; les huit premiers caractères doivent former une date `YYYYMMDD` valide. |
| `STMTTRN/TRNAMT` | `amount` | Obligatoire, signé, non nul et converti en `Decimal(18,2)`. |
| `STMTTRN/NAME`, `PAYEE/NAME` ou `MEMO` | `description` | Au moins une valeur est obligatoire. |
| `STMTTRN/CHECKNUM` ou `REFNUM` | `reference` | Facultatif. |

Les statuts OFX non nuls sont refusés. Le parseur `defusedxml` est utilisé pour rejeter les DTD, entités externes et charges XML dangereuses. Le contenu OFX est ensuite envoyé au même pipeline transactionnel que le CSV : hash de contenu, idempotence, verrous PostgreSQL, lignes de traçabilité, transactions canoniques et Audit atomique.
## Import MT940

L’endpoint `POST /api/v1/treasury/transactions/imports/mt940` utilise le même multipart, le même `treasury_bank_account_id`, le même en-tête `Idempotency-Key` et la même permission que l’import CSV. Il prend en charge le format **MT940 v1** avec un unique compte par fichier.

| Balise MT940 | Destination normalisée | Règle |
|---|---|---|
| `:20:` | Validation du relevé | Référence de message obligatoire. |
| `:25:` | Compte bancaire de Trésorerie | Doit être unique, non vide et correspondre au numéro de compte configuré après suppression des espaces. |
| `:60F:` / `:60M:` et `:62F:` / `:62M:` | Validation du relevé | Soldes d’ouverture et de clôture obligatoires. |
| `:61:` | Transaction bancaire | Date de valeur, date d’écriture, sens crédit/débit, montant et référence bancaire. |
| `:86:` | Libellé de transaction | Narration associée à la ligne `:61:` précédente lorsqu’elle est présente. |

Le montant MT940 utilise la virgule décimale et le signe est déterminé par le marqueur `C` ou `D`, y compris les marqueurs de contre-passation `RC` et `RD`. Une référence après le séparateur `//` sert d’identifiant externe stable. En son absence, FIP dérive un identifiant déterministe à partir des données normalisées de la ligne ; il n’invente aucun mouvement.

Le fichier est contrôlé avant persistance : balises essentielles, compte, lignes `:61:`, dates, montants, limites et unicité des références externes. Il est ensuite envoyé au même pipeline transactionnel que CSV et OFX : hash de contenu, idempotence, verrous PostgreSQL, déduplication, transactions canoniques, lignes d’import et Audit atomique.
