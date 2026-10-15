# Cloudflare D1 — déploiement expérimental (pas de production)

Le code D1 reste désactivé par défaut. Il ne faut pas modifier les secrets Vercel tant que la migration de données et les tests réels sur Cloudflare ne sont pas validés.

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

**Ne pas activer en production.** Il manque une procédure complète d'export/import des données Turso, un test intégral contre un vrai D1 (notamment les triggers de fencing, les limites de taille et les sauvegardes concurrentes), une recette des sessions/comptes et un plan de retour arrière. La sauvegarde actuelle envoie le batch dans une seule requête HTTP plafonnée à 2 Mo et au maximum 1000 lignes ; au-delà, elle échoue sans basculer silencieusement vers Turso.

Le Worker ne peut pas être déployé depuis GitHub sans rattachement explicite à un compte Cloudflare et création du binding D1.


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

**Attention :** la migration réelle n'est pas complète : ce script prépare un import à partir d'une sauvegarde ponctuelle; il ne réalise ni capture des dernières écritures, ni synchronisation en continu, ni commutation atomique Vercel/D1.
