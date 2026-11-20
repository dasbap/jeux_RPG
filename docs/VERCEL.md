# Déploiement Vercel et stockage Cloudflare D1

Le projet cible est `dasbaps-projects/jeux-rpg`. `fleet-test` ne doit pas être modifié.

Depuis la bascule du 6 novembre 2026, la production publique utilise **Cloudflare
D1 en UE**. Le SHA, les preuves du transfert et les vérifications navigateur sont
dans [D1_PRODUCTION.md](D1_PRODUCTION.md). Turso reste une source de récupération
verrouillée ; il n'est plus le backend actif.

L’application déployée expose `app:app`, une application FastAPI/ASGI créée par `jeuxRPG.multiplayer.realtime.create_app`. Le serveur HTTP local conserve son entrée dédiée. Python 3.12 et la région Francfort sont configurés.

## Variables Vercel

- `RPG_DATABASE_BACKEND=d1` : valeur active et requise pour la production actuelle. Le code conserve un défaut historique `turso` si cette variable manque ; ne pas l’omettre dans un environnement D1.
- En mode `d1` : `RPG_D1_WORKER_URL` et `RPG_D1_SERVICE_TOKEN`, identiques à ceux du Worker privé. Aucun identifiant Turso n'est requis.
- En mode `turso` : `TURSO_DATABASE_URL` (URL libSQL ou HTTPS) et `TURSO_AUTH_TOKEN` (lecture et écriture).
- `RPG_ADMIN_TOKEN` : secret aléatoire distinct, au moins 32 caractères, pour le panneau administrateur.
- `RPG_PUBLIC_ORIGIN` : origine HTTPS sans chemin si un domaine personnalisé est utilisé.
- `RPG_RUNTIME_MODE=d1` : moteur Vercel transactionnel, sans Redis ni processus
  persistant sur Render. Ce mode est aussi le défaut pour Vercel avec le backend D1.
  Les anciennes variables Redis/KV sont ignorées et retirées du build D1.

Configurer ces valeurs pour les environnements réellement déployés. La variable GitHub `RPG_DATABASE_BACKEND` et les paramètres D1 sont dans l’environnement `production`, pas nécessairement au niveau du dépôt. Les workflows conservent aussi un repli historique `turso` si la variable manque. Les previews doivent utiliser une base et un Worker distincts. Le workflow synchronise les paramètres nécessaires vers Vercel ; les secrets GitHub ne sont pas transmis automatiquement en dehors de cette procédure.

## Initialiser et contrôler le stockage

Dans GitHub Actions, sélectionner **Administration du stockage**, puis **Run workflow**, branche `prod`. Les opérations `connexion`, `schema` et `integrite` sont en lecture seule pour les deux backends. Ce workflow n'expose aucune initialisation ni suppression.

Le workflow de publication sur `prod` crée une sauvegarde du backend actif, vérifie sa restauration, la chiffre avec age et conserve uniquement sa copie chiffrée pendant trente jours dans GitHub. Il vérifie ensuite la base avant le build et la publication. Les variables du backend sont limitées aux étapes qui en ont besoin.

En production D1, renseigner `RPG_D1_WORKER_URL` et le secret `RPG_D1_SERVICE_TOKEN` dans l’environnement GitHub `production`. Les variables `TURSO_DATABASE_URL` et `TURSO_AUTH_TOKEN` ne concernent que l’ancien adaptateur et ses outils d’export ; elles ne sont pas requises par le moteur D1.

Pour Turso, l'initialisation transactionnelle existante intervient après la sauvegarde. Pour D1, le schéma et les triggers doivent être installés sur la cible avant publication ; le contrôle refuse un schéma incompatible et ne migre pas silencieusement la base. La procédure et les preuves de l'import réel sont dans [D1_PREPRODUCTION.md](D1_PREPRODUCTION.md).

## Administration

Ouvrir `/admin` sur le déploiement et saisir `RPG_ADMIN_TOKEN`. La clé reste en mémoire dans cet onglet ; elle n’est enregistrée ni dans le stockage navigateur ni dans les URL.

Le panneau permet de rechercher et renommer les identités de joueurs existantes, de les suspendre ou rétablir, et de révoquer leur jeton. Une révocation invalide définitivement l’ancien jeton ; aucun jeton de remplacement n’est remis par le panneau. Les comptes et leurs parties restent conservés. Les actions sont consignées dans `admin_audit`.

Le jeu dispose désormais de comptes nom d’utilisateur/mot de passe avec plusieurs personnages, sessions révocables, changement de mot de passe et déconnexion globale. Le panneau administrateur reste distinct et ne fournit pas encore de récupération de compte par email ni de rôles administrateurs individuels.

## Exécution et validation

Le nouveau mode Vercel utilise D1 comme état partagé. Chaque opération recharge
un snapshot cohérent, avance la simulation et applique la commande en SQLite en
mémoire, puis confirme atomiquement les changements dans D1 avant de répondre.
Le numéro de version est comparé dans la même transaction que les données : une
instance concurrente repart d'un snapshot neuf et rejoue la commande. Les reçus
de commandes rendent les reprises idempotentes. Le combat, les positions, le
chat, la présence et les limites de requêtes sont partagés entre instances.
Les connexions WebSocket sur `/api/ws` diffusent l'état confirmé ; aucun tick de
fond ni sauvegarde à l'arrêt de la fonction n'est nécessaire à la persistance.

Le Worker cible doit d'abord être mis à jour avec les opérations
`runtime_snapshot` et `commit_runtime` de `cloudflare/d1-worker.mjs`.
Le contrôle avant build exige `runtime_transactions=1`. Le schéma et les
anciennes sauvegardes restent compatibles. La bascule de production doit
arrêter les anciennes connexions et sauvegarder l'ancien moteur avant de
promouvoir le mode transactionnel ; une preview n'effectue pas cette bascule.

Le contrôle des fichiers ne contacte pas D1 ; l'étape de stockage et la recette
navigateur vérifient séparément le Worker réel. Le mode transactionnel effectue
deux appels D1 par opération, davantage en cas de conflit. Les snapshots complets
et les écritures de simulation augmentent la latence et les lectures/écritures
D1 par rapport au moteur persistant. La capacité et les quotas doivent être
mesurés sur la recette : les tests de correction ne prouvent pas une capacité
de 40 joueurs. Voir [ARCHITECTURE.md](ARCHITECTURE.md#mesures-disponibles-et-limites).

## Branche de publication

### Controle de publication et synchronisation des branches

Le job `quality` attend les huit controles requis par les protections GitHub
et `d1-worker` sur le SHA exact de `prod`. Un controle absent, ignore, annule,
en echec ou encore en cours interdit le deploiement. Ce job utilise uniquement
le jeton GitHub en lecture des checks ; il n'a aucun secret de production.

Apres la sauvegarde chiffree, le job `deploy` controle le Worker D1 avant de
modifier les variables Vercel. Le code `d1_worker_upgrade_required` indique
que le Worker cible n'expose pas encore les transactions atomiques. Relancer
la CI sans mettre a jour ce Worker ne corrige pas cette incompatibilite.
La mise a jour du Worker de production et l'arret des anciens moteurs restent
une operation de bascule distincte, avec sauvegarde et verification du stockage.
Le workflow ne remplace pas automatiquement le Worker de production.

Les synchronisations passent par des PR avec une fusion **merge**, afin de
conserver les ancetres des deux branches :

1. Avant une publication, integrer `prod` dans `master` si des commits de
   production n'y sont pas encore presents, puis attendre les controles.
2. Ouvrir la PR `master` vers `prod`, attendre les controles et fusionner.
   Cette fusion declenche la publication : elle doit respecter les prerequis
   D1 et la procedure de bascule ci-dessus.
3. Apres publication, reintegrer `prod` dans `master` par PR pour conserver
   le commit de fusion et eviter une prochaine PR en retard sur sa base.

Deux arbres identiques peuvent avoir des historiques differents. Ne pas
utiliser de push force, de reset distant ni de squash pour simuler cette
synchronisation. Les protections existantes restent actives.

### Recette Vercel des PR

Le workflow **Vercel preview et parcours navigateur** valide la configuration
sur chaque PR. Le job de déploiement utilise exclusivement le projet `jeux-rpg`
en Preview et le Worker fictif `jeux-rpg-d1-preview`. Il ne promeut aucun domaine.
Les recettes sont sérialisées car elles partagent la même base de test.

Configurer l'environnement GitHub `vercel-preview` avec les secrets
`VERCEL_PREVIEW_D1_SERVICE_TOKEN`, `VERCEL_PREVIEW_ADMIN_TOKEN` (distinct de la
production, au moins 32 caractères). Aucun secret Redis n'est nécessaire. Le secret
`VERCEL_TOKEN` du dépôt fournit l'accès au projet existant. Activer ensuite la
variable de dépôt `VERCEL_PREVIEW_ENABLED=1`. Sans cette variable, seul le job
de configuration s'exécute ; cela ne constitue pas une validation distante.
Les PR venant d'un fork n'exécutent pas le déploiement avec des secrets.

La recette construit l'artefact Vercel, déploie le SHA de tête exact, puis
contrôle par l'API authentifiée le projet, l'équipe, le SHA et l'environnement
avant de donner accès au navigateur. Elle vérifie l'inscription, le personnage,
l'aventure, son checkpoint et sa reprise après connexion par mot de passe,
l'authentification WebSocket, le solo avec reprise locale et le paysage imposé
sur téléphone. Les identifiants fictifs restent uniquement en mémoire du test ;
les comptes fictifs créés restent dans le D1 de test. L'artefact GitHub contient
l'URL, un rapport sans secrets et les captures du jeu.

L'accès à une preview protégée passe par le jeton OIDC de développement
temporaire obtenu avec `vercel env run`. Les en-têtes sont limités à l'origine
vérifiée. Le workflow ne désactive pas la protection Vercel et ne récupère pas
les variables de production. Le moteur et le site tournent sur Vercel, avec
le Worker D1 fictif pour la persistance. Render et Redis ne sont pas utilisés.

Le lancement manuel devient disponible lorsque le workflow est intégré à la
branche par défaut. Avant cela, les événements de PR exécutent déjà ce workflow.

`master` contient le code intégré. `prod` est la branche publiée par le workflow **Publication Vercel jeux-rpg** à chaque push, ainsi que lors d'un lancement manuel sur cette branche.

Le workflow restaure uniquement les secrets D1 et administrateur dans le build
local après `vercel pull`, dont les secrets sont remplacés par `[SENSITIVE]`.
Il configure `RPG_RUNTIME_MODE=d1`. Le moteur et ses tests de publication utilisent D1 pour la coordination.

Le workflow exécute les tests et contrôles du stockage, prépare un déploiement de production avec `--skip-domain`, contrôle son URL exacte et son `RPG_RELEASE_SHA`, puis promeut ce même déploiement. Le domaine public reste sur la précédente version tant que la vérification échoue. `VERCEL_TOKEN` et les accès D1 doivent correspondre au projet existant. Pour un déploiement protégé, fournir le secret `VERCEL_AUTOMATION_BYPASS_SECRET` au vérificateur.

Avant de lancer un workflow utilisant les secrets, protéger la branche et faire relire le code, ou configurer un reviewer requis de l’environnement GitHub `production` qui approuve le commit exact. La création de la branche ne configure pas ces règles et ne modifie pas le site public.

Les dépendances de CI sont contraintes par `constraints.txt`. Les limites mesurées localement ne constituent pas une capacité garantie du plan Vercel. Conserver une sauvegarde du D1 actif avant les migrations et vérifier sa restauration sur une base distincte. Ne pas promouvoir l’ancienne base Turso après des écritures D1 sans conserver cette progression.
