# RPG Python

Moteur RPG textuel : personnages, compétences, combats, progression, navigation, sauvegardes et simulations d'équilibrage.

## Installation et lancement

Python 3.10 ou supérieur.

```bash
git clone https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
python -m venv .venv
```

Activer l'environnement avec `source .venv/bin/activate` sur Linux/macOS ou `.venv\Scripts\Activate.ps1` sur PowerShell.

```bash
python -m pip install '.[test]'
python -m jeuxRPG --class Knight --floors 2 --seed 42
jeux-rpg --floors 2
python main.py --floors 2
```

Le lancement produit un rapport JSON de progression de tour ; le prototype ne fournit pas d'interface interactive ni de serveur HTTP.

## Exemple

```python
from jeuxRPG._class.character import Character
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG.game_engine import GameEngine

hero = Character.create("Knight", "hero", "Héros")
enemy = Character.create("Goblin", "enemy", "Gobelin")
GameEngine().run_fights([Fight(hero, enemy)], timeout=5)
```

Le code est désormais regroupé dans le paquet `jeuxRPG/`. Les chemins d'import `jeuxRPG.*` sont conservés ; les accès directs aux anciens dossiers racine doivent être adaptés.

## Vérifications

```bash
ruff check .
python -m compileall -q jeuxRPG main.py scripts
python -m pytest -m 'not performance' --cov=jeuxRPG --cov-report=json --cov-report=xml
python scripts/function_audit.py
python -m pytest test/performance --junitxml=performance.xml -o junit_family=legacy
python -m jeuxRPG._balance.run_simulation --mode matrix --matches 2
```

Quatre workflows GitHub Actions couvrent lint/syntaxe, tests sur Linux et Windows avec Python 3.10/3.12/3.13, distribution installée hors dépôt, et performance du moteur. Les rapports sont disponibles en artefacts.

La couverture mesure les lignes et branches, avec un minimum de 75 %. L'inventaire `function-audit.json` associe chaque fonction à son rôle documenté et aux lignes exécutées/manquantes. Une ligne exécutée ne prouve pas que tous ses comportements sont validés.

Les tests marqués `external` nécessitent `bot.game.storage`, application absente de ce dépôt ; ils sont explicitement ignorés lorsqu'elle manque. Deux tests historiques sont également désactivés. Les benchmarks mesurent 500 créations de personnages et 100 duels ; les budgets (5 s/100 créations, 10 s/100 duels, 64 Mio de pic mémoire) détectent des dégradations importantes, pas une petite régression par rapport à une machine de référence.

Les anciens scénarios Locust ont été retirés : ils visaient un serveur web absent et acceptaient des erreurs HTTP 500 comme des succès. Le benchmark exerce directement le moteur RPG.

## Aventure continue et craft

`python main.py` lance désormais une arène sans limite avec reprise automatique de sauvegarde, butin de créatures, armures, bonus de panoplie et craft automatique. `Ctrl+C` arrête après le combat en cours. `python main.py --interactive` permet de fabriquer et équiper les objets manuellement. Pour une exécution limitée : `python main.py --battles 10 --interval 0`.

Voir [ADVENTURE.md](ADVENTURE.md) pour les commandes, recettes, règles de défaite, sauvegardes et critères des panoplies. Les commandes historiques utilisant `--floors` conservent la simulation courte.
