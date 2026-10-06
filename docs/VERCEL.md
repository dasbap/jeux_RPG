# Alpha Vercel / Turso

Le projet cible est `dasbaps-projects/jeux-rpg`. `fleet-test` ne doit pas être modifié.

L’application WSGI est `app:app`, déclarée dans `pyproject.toml`. Le serveur local conserve son entrée `main.py`. Python 3.12 et la région Francfort sont configurés.

## Variables Vercel

- `TURSO_DATABASE_URL` : URL libSQL ou HTTPS de la base existante.
- `TURSO_AUTH_TOKEN` : secret de cette base avec lecture et écriture.
- `RPG_ADMIN_TOKEN` : secret aléatoire distinct, au moins 32 caractères, pour le panneau administrateur.
- `RPG_PUBLIC_ORIGIN` : origine HTTPS sans chemin si un domaine personnalisé est utilisé.

Configurer ces valeurs pour les environnements réellement déployés. Les previews doivent utiliser une base distincte pour isoler les données. Les secrets GitHub ne sont pas transmis automatiquement à Vercel.

## Initialiser Turso

Dans GitHub Actions, sélectionner **Administration Turso**, puis **Run workflow**, branche `alpha-vercel-turso`, opération `connexion`, puis `initialiser`. Le workflow doit déjà être présent sur la branche par défaut pour apparaître dans l’interface.

Sur `alpha-vercel-turso` uniquement, un push modifiant `multiplayer/schema.py` ou ce workflow lance aussi connexion, initialisation et intégrité. Les autres branches conservent le lancement manuel.

`TURSO_DATABASE_URL` doit être un secret ou une variable GitHub Actions ; `TURSO_AUTH_TOKEN` doit être un secret Actions. Un jeton de base donne accès à une base existante ; il ne permet pas de créer une nouvelle base dans une organisation Turso.

L’initialisation est transactionnelle et réexécutable. Elle conserve les comptes, parties et données existants. Elle crée les tables du moteur, les statuts de comptes, le journal admin, les connexions de chat et les limites de requêtes. Aucun SQL libre ni action de suppression n’est exposé par ce workflow.

## Administration

Ouvrir `/admin` sur le déploiement et saisir `RPG_ADMIN_TOKEN`. La clé reste en mémoire dans cet onglet ; elle n’est enregistrée ni dans le stockage navigateur ni dans les URL.

Le panneau permet de rechercher et renommer les identités de joueurs existantes, de les suspendre ou rétablir, et de révoquer leur jeton. Une révocation invalide définitivement l’ancien jeton ; aucun jeton de remplacement n’est remis par le panneau. Les comptes et leurs parties restent conservés. Les actions sont consignées dans `admin_audit`.

Les identités actuelles du jeu reposent sur des jetons générés lors de la création de personnages. Ce panneau ne crée pas encore un système d’inscription email/mot de passe, de récupération de compte ou de rôles administrateurs individuels.

## Exécution et validation

La simulation avance lors des requêtes des joueurs, sans thread permanent. Les transactions, reçus de commandes, chat et limites sont partagés dans Turso. Aucun état de jeu durable n’est sauvegardé sur le disque Vercel. La migration est également exécutée au premier accès d’une instance.

Le contrôle avant build vérifie les fichiers et les variables sans afficher les secrets. Il ne valide pas la connexion distante. Après déploiement, vérifier inscription, reprise de partie, combat, chat entre deux navigateurs, suspension/rétablissement et conservation des données après redéploiement. La charge de 30 joueurs et les quotas Turso gratuits restent à mesurer sur une preview.
