# Cloudflare D1 — production et préproduction

La production publique utilise désormais D1 en UE. Les données, les sauvegardes,
le déploiement Vercel et le parcours navigateur ont été vérifiés ; voir
[D1_PRODUCTION.md](../docs/D1_PRODUCTION.md). Les configurations anciennes sans
sélection explicite restent compatibles avec Turso ; le backend de production
est explicitement `RPG_DATABASE_BACKEND=d1`.

La préproduction `jeux-rpg-preview` et son Worker sont maintenant déployés en UE.
La recette réelle avec compte fictif passe : sauvegarde, reprise, reconnexion,
rejet du moteur périmé et rollback atomique. Voir
[les preuves et les étapes restantes](../docs/D1_PREPRODUCTION.md).

## Fonctionnement

- `cloudflare/d1-worker.mjs` : Worker privé, authentification par jeton, lecture cohérente par session primaire et sauvegarde atomique via D1 `batch()`.
- `cloudflare/0004_fence_guard.sql` : triggers empêchant une instance périmée d'écraser la progression d'une plus récente. **Ce fichier est obligatoire**.
- `jeuxRPG/multiplayer/d1_client.py` : adaptateur HTTP Python.
- `RPG_DATABASE_BACKEND=d1` active ce backend. Sans cela, Turso fonctionne comme avant.

## Provisionnement manuel d'une base de test

Créer une base D1 isolée avec juridiction UE :

```bash
npx wrangler d1 create jeux-rpg-preview --jurisdiction eu
```

Créer un projet Worker depuis `cloudflare/d1-worker.mjs` et configurer son binding `DB` avec l'identifiant exact de cette base, puis définir le secret de service :

```bash
npx wrangler secret put RPG_D1_SERVICE_TOKEN
npx wrangler deploy
```

Les fichiers SQL `jeuxRPG/multiplayer/migrations/0001_initial.sql`, `0002_receipt_expiry.sql`, `0003_guilds.sql` doivent être exécutés **dans cet ordre sur D1 de test**, avant `cloudflare/0004_fence_guard.sql`, avec `wrangler d1 execute <nom-base> --remote --file <fichier>`. Les trois migrations du jeu doivent être testées en pratique sur D1. Il faut créer la table `schema_version` et y inscrire la version 3 (une seule ligne `id=1`) selon `schema.py`, puis vérifier les tables et les références. Préparer cette initialisation sur une copie de test, sans improviser sur la production. Ne pas exécuter ces commandes sur Turso.

## Configuration de préproduction Vercel seulement

```text
RPG_DATABASE_BACKEND=d1
RPG_D1_WORKER_URL=https://<worker>.workers.dev/
RPG_D1_SERVICE_TOKEN=<secret identique au Worker>
```

Le Worker n'a pas d'endpoint d'administration ni de SQL arbitraire. L'API est protégée par un secret partagé, mais l'accès au domaine workers.dev doit aussi être restreint selon la politique d'exploitation.

## Limites restantes

La bascule finale de production et la recette Vercel sont validées. Le transfert
conserve les 707 lignes durables initiales, les séquences, les relations et la
reprise ; une sauvegarde D1 a été restaurée. Un retour vers Turso exige de
conserver les nouvelles écritures D1 avant toute réactivation de l'ancienne base.
Les tests de comptes et de sauvegarde concurrente passent
sur D1 réel avec des données fictives. La sauvegarde actuelle envoie le batch
dans une seule requête HTTP plafonnée à 2 Mo et au maximum 1000 lignes ; au-delà,
elle échoue sans basculer silencieusement vers Turso.

Le Worker ne peut pas être déployé depuis GitHub sans rattachement explicite à un compte Cloudflare et création du binding D1.

Le déploiement local de recette est reproductible avec
`python -m scripts.deploy_d1_preview`, qui utilise la connexion Wrangler existante,
et `python -m scripts.verify_d1_preview --env-file .data/d1-migration/preview.env`.
Ce dernier script exige une base contenant uniquement des métadonnées et ne doit
pas être utilisé après l'import des comptes réels. Le contrôle d'import est
`python -m scripts.verify_d1_import SOURCE --env-file ENV_D1` ; il reste en lecture seule.


## Export des données réelles (étape hors production)

**Ne jamais importer tant que la préproduction D1 n'a pas été testée.** La base D1 doit être dédiée à la recette et ne contenir aucune donnée utilisateur. Toute bascule nécessite de geler les écritures, refaire un export final, valider l'import et sauvegarder Turso.

Dans PowerShell, depuis la branche `migration/cloudflare-d1-design`, configurer `TURSO_DATABASE_URL` et `TURSO_AUTH_TOKEN` localement sans les enregistrer dans Git, puis :

```powershell
python -m scripts.export_turso_backup .\\turso-private.sqlite3
python -m scripts.prepare_d1_import .\\turso-private.sqlite3 .\\d1-private-import.sql
```

Le fichier `d1-private-import.sql` contient des données personnelles et des empreintes de mots de passe. Le conserver hors Git, ne pas le communiquer dans les tickets ni dans les journaux publics. Les scripts refusent d'écraser un fichier existant.

Après avoir vérifié que la cible D1 de **préproduction uniquement** est vide (en dehors des tables), importer :

```powershell
npx wrangler d1 execute jeux-rpg-preview --remote --file .\\d1-private-import.sql
```

Le script génère un `PRAGMA defer_foreign_keys=ON`, suivi d'insertions avec littéraux SQLite; la base cible doit déjà contenir les tables et `schema_version=3`. Vérifier que le CLI accepte le fichier et que les décomptes de lignes correspondent au rapport JSON produit. Après l'import, réaliser des tests réels de lecture, sauvegarde, concurrence et reprise avec le Worker.

Le générateur ouvre un instantané en lecture seule et refuse une version de schéma
différente de celle du serveur, une table obligatoire absente ou des références
invalides. Il vérifie les relations de toute la sauvegarde, mais exporte uniquement
les tables durables du moteur (`TABLES`) ; chat, présence et limites transitoires
restent exclus. Un test local vérifie la conservation des lignes et la reprise
d'une partie après import.

## Vérifications locales

```powershell
python -m pytest test/test_d1_client.py test/test_d1_import.py -q
node scripts/verify_d1_worker.mjs
```

Le second contrôle nécessite Node 24 et utilise SQLite local avec une simulation
du binding D1. Il couvre un lot où l'enfant précède le parent, le refus d'un moteur
périmé et l'annulation de tout le lot si une relation est invalide. Le Worker diffère
les clés étrangères jusqu'à la fin du lot atomique ; il ne les désactive pas.
Ces contrôles passent aussi en CI et ne certifient pas le service Cloudflare réel.

Les sources contractuelles et les limites gratuites vérifiées lors de la reprise
sont consignées dans [le dossier fournisseur](../docs/CLOUDFLARE_DATA_PROCESSING.md).

**Attention :** la migration réelle n'est pas complète : ce script prépare un import à partir d'une sauvegarde ponctuelle; il ne réalise ni capture des dernières écritures, ni synchronisation en continu, ni commutation atomique Vercel/D1.


## Export sécurisé via GitHub Actions (sans secrets Turso sur le PC)

Le workflow `.github/workflows/export-turso-d1.yml`, intégré par la PR #90, lit les secrets Turso du dépôt. Il s'exécute uniquement manuellement depuis la branche protégée `master`. Il crée un export vérifié puis chiffré, sans écriture dans la base source.

1. Installer `age` localement et créer une paire de clés : `age-keygen -o d1-migration-key.txt`. Conserver ce fichier privé hors du dépôt et dans un coffre sécurisé.
2. Enregistrer uniquement la clé publique `age1...` dans les variables Actions du dépôt sous le nom `D1_MIGRATION_BACKUP_RECIPIENT`. La clé privée ne quitte pas le poste.
3. Vérifier que les secrets de dépôt `TURSO_DATABASE_URL` et `TURSO_AUTH_TOKEN` existent.
4. Lancer **Actions > Export prive Turso pour migration D1 > Run workflow**, branche `master`.
5. Télécharger l'artefact `d1-private-source` (rétention sept jours), vérifier `export-checksum.txt`, puis déchiffrer localement `d1-source.sqlite3.age`. Générer ensuite le SQL avec `prepare_d1_import.py` dans un dossier privé.

Le workflow ne modifie aucune base. Les fichiers SQL déchiffrés contiennent les données personnelles des joueurs, comptes et hashes de mots de passe : ne pas les committer, les joindre à une issue, ni les partager dans le chat. Le fichier de clé privée ne doit pas être chargé dans GitHub.

**Ne pas fusionner l'ensemble de la PR en production uniquement pour déclencher ce workflow tant que les tests du code D1 ne sont pas terminés.** Le workflow peut être isolé dans une PR dédiée puis fusionné séparément après revue.

Un export pendant que les joueurs continuent d'écrire n'est qu'une photographie temporaire. Il ne doit jamais servir à une bascule finale sans gel des écritures, nouvelle sauvegarde et contrôle des écarts.
