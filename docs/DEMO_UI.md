# Parcours automatique par le client

Depuis le dépôt installé avec `python -m pip install .`, installer Node.js puis les dépendances du client de test :

```sh
npm install --prefix .ui-test jsdom@26.1.0
```

Sous PowerShell :

```powershell
$env:NODE_PATH = "$PWD\.ui-test\node_modules"
python scripts/demo_authored_ui.py
```

Sous Linux :

```sh
NODE_PATH="$PWD/.ui-test/node_modules" python scripts/demo_authored_ui.py
```

Le serveur utilise les fichiers actuels du dossier `maps`, dans une base temporaire distincte des parties existantes. Le pilote exécute le vrai JavaScript du jeu dans un DOM jsdom et effectue des clics, doubles clics et soumissions de formulaires. Il ne transmet jamais directement une commande de jeu et ne modifie ni les personnages, ni les récompenses, ni les quêtes côté serveur. Les snapshots client sont consultés pour choisir les actions et vérifier les résultats.

Le parcours crée un chevalier et un prêtre, explore la clairière et la forêt, rejoint Rosée par les chemins rapides, approche Mira, accepte la quête, lit son nombre d'ennemis requis, rejoint la chasse, revient rendre la quête, fabrique et équipe la veste pour les deux personnages, puis rejoint Brume. Le groupe peut reprendre le parcours après le secours prévu par le jeu. Le pilote s'arrête en erreur en cas d'accès impossible, de PNJ absent ou de progression bloquée. La limite globale est de trente minutes.

Par défaut, les durées du jeu sont conservées. `RPG_DEMO_SPEED` permet d'accélérer uniformément l'horloge pour le diagnostic ; une exécution accélérée ne remplace pas la vérification aux durées normales.

jsdom vérifie les interactions et l'état de l'interface, pas les pixels rendus par un navigateur. Les régressions des textures sont contrôlées séparément par `verify_http_ui.py`, qui vérifie la conservation des définitions SVG et des cases de pont lors des actualisations. Ce parcours complète les tests déterministes sur le monde de référence, il ne les remplace pas.
