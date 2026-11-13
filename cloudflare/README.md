# Cloudflare D1 — production et outils de recette

La production utilise **Cloudflare D1 en UE depuis le 6 novembre 2026**.
Le [rapport de bascule](../docs/D1_PRODUCTION.md) conserve les preuves du
transfert et de la restauration. L’[architecture actuelle](../docs/ARCHITECTURE.md)
distingue production D1, serveur local SQLite et solo hors ligne.

## Fichiers et protocole

- `d1-worker.mjs` : Worker privé, authentification serveur par jeton, lectures
  cohérentes et sauvegardes atomiques via D1 `batch()`.
- `0004_fence_guard.sql` : triggers obligatoires contre les générations de
  moteur périmées.
- `wrangler.production.json` et `wrangler.preview.json` : bindings et cibles
  distinctes. Ne pas confondre une recette et la base des joueurs.
- `../jeuxRPG/multiplayer/d1_client.py` : adaptateur HTTP Python appelé par le
  moteur pour charger et persister ses lots.

Les opérations sont `health`, `read_snapshot`, `load_snapshot` et
`persist_checkpoint`. Le Worker n’expose ni migration de schéma ni SQL
arbitraire. Les sauvegardes sont bornées à 1000 changements par lot et la
taille de la requête est contrôlée par le Worker (seuil de 2 000 000 pour
le Content-Length et la longueur du texte reçu). Un refus
ne déclenche aucun retour automatique vers Turso.

## Configuration

```text
RPG_DATABASE_BACKEND=d1
RPG_D1_WORKER_URL=https://<worker-prive>.workers.dev
RPG_D1_SERVICE_TOKEN=<secret-identique-au-Worker>
```

Ces paramètres sont côté serveur, avec Redis et les autres variables décrites
dans [VERCEL.md](../docs/VERCEL.md). L’absence de sélection explicite garde
encore le défaut historique Turso dans le code ; toujours définir `d1` pour
un environnement D1. Le client du joueur ne reçoit aucun secret de service.

## Recette sur une base isolée

Les outils sont disponibles dans `master` ; aucune branche de migration
supplémentaire n’est nécessaire. La procédure et les résultats datés sont
dans [D1_PREPRODUCTION.md](../docs/D1_PREPRODUCTION.md).

`python -m scripts.deploy_d1_preview` utilise la connexion Wrangler locale
pour préparer une préproduction. L’initialisation applique les trois migrations
du jeu, la version de schéma 3 et les triggers de génération.

`python -m scripts.verify_d1_preview --env-file .data/d1-migration/preview.env`
crée des données fictives et exige une base ne contenant que des métadonnées.
Ne pas l’exécuter sur la production ni sur une cible contenant des comptes
importés. Pour comparer un import existant en lecture seule :

```powershell
python -m scripts.verify_d1_import SOURCE --env-file ENV_D1
```

Les fichiers d’environnement, SQL privés, exports et clés de chiffrement
restent hors Git. Un export ponctuel n’est pas une synchronisation continue.

## Tests locaux sans accès Cloudflare

```powershell
python -m pytest test/test_d1_client.py test/test_d1_import.py -q
node scripts/verify_d1_worker.mjs
```

Le test du Worker utilise Node 24, SQLite local et un binding D1 simulé.
Il couvre notamment les clés étrangères, le rejet d’une génération périmée
et le rollback des lots invalides. Il ne certifie ni le service distant ni
les quotas réels.

## Sauvegardes et ancien export Turso

La publication `prod` sauvegarde le backend configuré, actuellement D1,
vérifie sa restauration et conserve l’archive chiffrée trente jours dans
GitHub Actions. Le Worker doit être déployé séparément avec le binding et le
secret correspondant à la cible choisie.

`export-turso-d1.yml` est un outil historique manuel sur `master`, pas le
workflow de sauvegarde courant de D1. Sans option de gel ou de restauration
de génération, l’export de la source Turso est en lecture seule puis chiffré
avec age ; l’artefact est conservé sept jours. Les options `freeze_writes`
et `restore_fence` modifient le verrou de la source : le workflow entier ne
doit donc pas être présenté comme toujours sans écriture.

Turso reste une source verrouillée. Après les écritures de joueurs sur D1,
ne pas utiliser `restore_fence` pour réactiver l’ancienne base : la progression
D1 doit d’abord être préservée. Voir la [procédure de récupération](../docs/D1_PRODUCTION.md#exploitation-et-récupération).
