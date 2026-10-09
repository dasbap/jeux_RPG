# Déploiement Vercel / Turso

Le projet cible est `dasbaps-projects/jeux-rpg`. `fleet-test` ne doit pas être modifié.

L’application déployée expose `app:app`, une application FastAPI/ASGI créée par `jeuxRPG.multiplayer.realtime.create_app`. Le serveur HTTP local conserve son entrée dédiée. Python 3.12 et la région Francfort sont configurés.

## Variables Vercel

- `TURSO_DATABASE_URL` : URL libSQL ou HTTPS de la base existante.
- `TURSO_AUTH_TOKEN` : secret de cette base avec lecture et écriture.
- `RPG_ADMIN_TOKEN` : secret aléatoire distinct, au moins 32 caractères, pour le panneau administrateur.
- `RPG_PUBLIC_ORIGIN` : origine HTTPS sans chemin si un domaine personnalisé est utilisé.
- `REDIS_URL` ou `KV_URL` : Redis partagé pour coordination temps réel, présence et rate limiting distribué.

Configurer ces valeurs pour les environnements réellement déployés. Les previews doivent utiliser une base distincte pour isoler les données. Les secrets GitHub ne sont pas transmis automatiquement à Vercel.

## Initialiser Turso

Dans GitHub Actions, sélectionner **Administration Turso**, puis **Run workflow**, branche `deploy/production`, opération `connexion`, puis `initialiser`. Le workflow doit déjà être présent sur la branche par défaut pour apparaître dans l’interface.

Les opérations de production sont manuelles depuis `deploy/production`. Aucun push ne publie automatiquement le jeu. La migration additive `0002_receipt_expiry.sql` conserve les comptes et ajoute une expiration au journal transitoire.

`TURSO_DATABASE_URL` doit être un secret ou une variable GitHub Actions ; `TURSO_AUTH_TOKEN` doit être un secret Actions. Un jeton de base donne accès à une base existante ; il ne permet pas de créer une nouvelle base dans une organisation Turso.

L’initialisation est transactionnelle et réexécutable. Elle conserve les comptes, parties et données existants. Elle crée les tables du moteur, les statuts de comptes, le journal admin, les connexions de chat et les limites de requêtes. Aucun SQL libre ni action de suppression n’est exposé par ce workflow.

## Administration

Ouvrir `/admin` sur le déploiement et saisir `RPG_ADMIN_TOKEN`. La clé reste en mémoire dans cet onglet ; elle n’est enregistrée ni dans le stockage navigateur ni dans les URL.

Le panneau permet de rechercher et renommer les identités de joueurs existantes, de les suspendre ou rétablir, et de révoquer leur jeton. Une révocation invalide définitivement l’ancien jeton ; aucun jeton de remplacement n’est remis par le panneau. Les comptes et leurs parties restent conservés. Les actions sont consignées dans `admin_audit`.

Le jeu dispose désormais de comptes nom d’utilisateur/mot de passe avec plusieurs personnages, sessions révocables, changement de mot de passe et déconnexion globale. Le panneau administrateur reste distinct et ne fournit pas encore de récupération de compte par email ni de rôles administrateurs individuels.

## Exécution et validation

La production utilise un moteur temps réel coordonné par Redis avec WebSocket sur `/api/ws`. Un propriétaire actif maintient l’état en mémoire, publie les changements et persiste les checkpoints vers Turso avec fencing ; les autres instances relaient les requêtes via Redis. Aucun état durable n’est sauvegardé sur le disque Vercel. Les migrations versionnées sont appliquées à l’initialisation.

Le contrôle avant build vérifie les fichiers et les variables sans afficher les secrets. Il ne valide pas la connexion distante. Après déploiement, vérifier inscription, reprise de partie, chargement de tous les modules frontend, WebSocket, combat, chat entre deux navigateurs, suspension/rétablissement et conservation des données après redéploiement. La CI contient également un smoke test de charge configurable ; les limites réelles du plan Turso/Redis doivent encore être validées sur une preview de production.

## Branche de publication

`master` contient le code intégré. `deploy/production` désigne une révision prête à publier. Pour la mettre à jour, fusionner une révision validée de `master` sans réécrire son historique. Lancer **Publication Vercel jeux-rpg** manuellement sur cette branche.

Le workflow exécute les tests et migrations, prépare un déploiement de production avec `--skip-domain`, contrôle son URL exacte et son `RPG_RELEASE_SHA`, puis promeut ce même déploiement. Le domaine public reste sur la précédente version tant que la vérification échoue. `VERCEL_TOKEN`, les accès Turso et les accès Redis doivent correspondre au projet existant. Pour un déploiement protégé, fournir le secret `VERCEL_AUTOMATION_BYPASS_SECRET` au vérificateur.

Avant de lancer un workflow utilisant les secrets, protéger la branche et faire relire le code, ou configurer un reviewer requis de l’environnement GitHub `production` qui approuve le commit exact. La création de la branche ne configure pas ces règles et ne modifie pas le site public.

Les dépendances de CI sont contraintes par `constraints.txt`. Les limites mesurées localement ne constituent pas une capacité garantie du plan Vercel. Conserver une sauvegarde Turso avant les migrations et vérifier la restauration sur une base distincte.
