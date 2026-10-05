# Préparation du premier déploiement Vercel

La branche `secure-multiplayer-poc` contient le serveur local. L’adaptation WSGI/Turso n’est pas encore publiée. Ne pas lancer un déploiement du jeu avant sa publication.

Les fichiers préparés sont :

- `.vercelignore` : exclut secrets locaux, sauvegardes, bases SQLite, logs, environnements virtuels, tests, outils de démonstration et dossiers temporaires des uploads Vercel.
- `.python-version` : sélectionne Python 3.12.
- `vercel.json` : choisit Francfort et exécute `scripts/check_vercel.py` avant le build.
- `scripts/check_vercel.py` : interrompt le build lorsque les fichiers de l’adaptation, l’entrée Python ou les variables Turso manquent. Il n’affiche pas les valeurs des secrets.

Le contrôle échoue actuellement volontairement, car `app.py`, `multiplayer/serverless.py`, `multiplayer/turso.py` et l’entrée `tool.vercel.entrypoint` manquent. Il faudra également installer le paquet du jeu et les dépendances du runtime via `requirements.txt`, puis configurer le runtime et les exclusions du bundle de fonctions une fois son entrée publiée. `.vercelignore` ne remplace pas ces vérifications du bundle.

Les dossiers `maps`, `_class`, `_core`, `_function`, `_balance`, `game_engine`, `multiplayer`, `i18n`, ainsi que `setup.py`, `pyproject.toml` et `requirements.txt`, sont conservés.

Dans Vercel, utiliser un projet distinct `jeux-rpg`, l’équipe `dasbaps-projects`, la racine du dépôt et la branche de production `secure-multiplayer-poc`. Laisser `fleet-test` intact.

Ajouter dans les variables du projet `TURSO_DATABASE_URL` et `TURSO_AUTH_TOKEN`. Le jeton doit permettre la lecture et l’écriture sur la base libSQL. Les previews doivent utiliser une base séparée si leurs données doivent être isolées de la production. Ne pas enregistrer ces secrets dans Git.

Après publication de l’adaptation, vérifier sur une preview l’inscription, les sessions entre deux navigateurs, un combat, le chat et la reprise des données après redéploiement. La présence de fichiers et de variables ne valide pas une connexion Turso ni les performances de 30 joueurs.
