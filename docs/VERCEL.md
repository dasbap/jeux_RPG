# Déploiement Vercel et stockage D1/Turso

Le projet cible est `dasbaps-projects/jeux-rpg`. `fleet-test` ne doit pas être modifié.

L’application déployée expose `app:app`, une application FastAPI/ASGI créée par `jeuxRPG.multiplayer.realtime.create_app`. Le serveur HTTP local conserve son entrée dédiée. Python 3.12 et la région Francfort sont configurés.

## Variables Vercel

- `RPG_DATABASE_BACKEND` : `d1` pour Cloudflare D1, `turso` pour le stockage historique. Sans valeur, les déploiements existants restent sur Turso jusqu'à la bascule validée.
- En mode `d1` : `RPG_D1_WORKER_URL` et `RPG_D1_SERVICE_TOKEN`, identiques à ceux du Worker privé. Aucun identifiant Turso n'est requis.
- En mode `turso` : `TURSO_DATABASE_URL` (URL libSQL ou HTTPS) et `TURSO_AUTH_TOKEN` (lecture et écriture).
- `RPG_ADMIN_TOKEN` : secret aléatoire distinct, au moins 32 caractères, pour le panneau administrateur.
- `RPG_PUBLIC_ORIGIN` : origine HTTPS sans chemin si un domaine personnalisé est utilisé.
- `REDIS_URL` ou `KV_URL` : Redis partagé pour coordination temps réel, relais entre instances et limites de connexion. La présence et l'état du moteur autoritaire restent en RAM ; les sauvegardes vont dans le stockage sélectionné.
- `REDIS_URLS` : liste JSON facultative d'URL Redis ; a priorité sur les deux variables précédentes.
- `RPG_REDIS_ACTIVE_INDEX` : index de l'instance active dans cette liste, à partir de 0. Le moteur et les autres services Redis utilisent tous cet index.

Configurer ces valeurs pour les environnements réellement déployés. Les previews doivent utiliser une base distincte pour isoler les données. Les secrets GitHub ne sont pas transmis automatiquement à Vercel.

## Initialiser et contrôler le stockage

Dans GitHub Actions, sélectionner **Administration du stockage**, puis **Run workflow**, branche `prod`. Les opérations `connexion`, `schema` et `integrite` sont en lecture seule pour les deux backends. Ce workflow n'expose aucune initialisation ni suppression.

Le workflow de publication sur `prod` crée une sauvegarde du backend actif, vérifie sa restauration, la chiffre avec age et conserve uniquement sa copie chiffrée pendant trente jours dans GitHub. Il vérifie ensuite la base avant le build et la publication. Les variables du backend sont limitées aux étapes qui en ont besoin.

`TURSO_DATABASE_URL` doit être un secret ou une variable GitHub Actions ; `TURSO_AUTH_TOKEN` doit être un secret Actions. Un jeton de base donne accès à une base existante ; il ne permet pas de créer une nouvelle base dans une organisation Turso.

Pour Turso, l'initialisation transactionnelle existante intervient après la sauvegarde. Pour D1, le schéma et les triggers doivent être installés sur la cible avant publication ; le contrôle refuse un schéma incompatible et ne migre pas silencieusement la base. La procédure et les preuves de l'import réel sont dans [D1_PREPRODUCTION.md](D1_PREPRODUCTION.md).

## Administration

Ouvrir `/admin` sur le déploiement et saisir `RPG_ADMIN_TOKEN`. La clé reste en mémoire dans cet onglet ; elle n’est enregistrée ni dans le stockage navigateur ni dans les URL.

Le panneau permet de rechercher et renommer les identités de joueurs existantes, de les suspendre ou rétablir, et de révoquer leur jeton. Une révocation invalide définitivement l’ancien jeton ; aucun jeton de remplacement n’est remis par le panneau. Les comptes et leurs parties restent conservés. Les actions sont consignées dans `admin_audit`.

Le jeu dispose désormais de comptes nom d’utilisateur/mot de passe avec plusieurs personnages, sessions révocables, changement de mot de passe et déconnexion globale. Le panneau administrateur reste distinct et ne fournit pas encore de récupération de compte par email ni de rôles administrateurs individuels.

## Exécution et validation

La production utilise un moteur temps réel coordonné par Redis avec WebSocket sur `/api/ws`. Un propriétaire actif maintient l’état en mémoire, publie les changements et persiste les checkpoints vers le backend sélectionné avec fencing ; les autres instances relaient les requêtes via Redis. Les moteurs D1 utilisent un espace de coordination distinct par URL de Worker. Aucun état durable n’est sauvegardé sur le disque Vercel.

Le contrôle avant build vérifie les fichiers et les variables sans afficher les secrets. Il ne valide pas la connexion distante. Après déploiement, vérifier inscription, reprise de partie, chargement de tous les modules frontend, WebSocket, combat, chat entre deux navigateurs, suspension/rétablissement et conservation des données après redéploiement. La CI contient également un smoke test de charge configurable ; les limites réelles du plan Turso/Redis doivent encore être validées sur une preview de production.

## Branche de publication

`master` contient le code intégré. `prod` est la branche publiée par le workflow **Publication Vercel jeux-rpg** à chaque push, ainsi que lors d'un lancement manuel sur cette branche.

Pour configurer plusieurs instances, ajouter le secret `REDIS_URLS` et la variable `RPG_REDIS_ACTIVE_INDEX` dans l'environnement GitHub `production`. Le workflow les synchronise vers Vercel et restaure les secrets CI pour le build local, car les secrets Vercel récupérés par `vercel pull` sont remplacés par `[SENSITIVE]`. La procédure de bascule et la reprise depuis Turso sont décrites dans [realtime.md](realtime.md#plusieurs-url-redis).

Le workflow exécute les tests et contrôles du stockage, prépare un déploiement de production avec `--skip-domain`, contrôle son URL exacte et son `RPG_RELEASE_SHA`, puis promeut ce même déploiement. Le domaine public reste sur la précédente version tant que la vérification échoue. `VERCEL_TOKEN`, les accès du backend sélectionné et les accès Redis doivent correspondre au projet existant. Pour un déploiement protégé, fournir le secret `VERCEL_AUTOMATION_BYPASS_SECRET` au vérificateur.

Avant de lancer un workflow utilisant les secrets, protéger la branche et faire relire le code, ou configurer un reviewer requis de l’environnement GitHub `production` qui approuve le commit exact. La création de la branche ne configure pas ces règles et ne modifie pas le site public.

Les dépendances de CI sont contraintes par `constraints.txt`. Les limites mesurées localement ne constituent pas une capacité garantie du plan Vercel. Conserver une sauvegarde Turso avant les migrations et vérifier la restauration sur une base distincte.
