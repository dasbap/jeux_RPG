# 🧙‍♂️ RPG Python – Projet personnel

Ce projet est un prototype de jeu de rôle (RPG) textuel développé en Python. Il intègre un système de combat en équipe, des classes de personnages (guerrier, mage, nécromancien...), un système de montée en niveau, et des compétences spéciales.

---

## ⚔️ Fonctionnalités

- Création de personnages avec statistiques et spécialités
- Système d'expérience, de niveau et de progression
- Combat automatique ou manuel en équipe
- Utilisation de compétences avec gestion de cooldown et d’énergie
- Log de combat tour par tour

---

## 📁 Structure du projet

- `main.py` : point d’entrée principal
- `_class/` : logique métier du jeu (personnages, combats, etc.)
- `test.py` : script de test (combat, action, etc.)

---

## ▶️ Exemple d'utilisation

```python
from jeuxRPG._class._event.confrontation.encounter.team_battle import TeamBattle
from jeuxRPG._class.character import Character
from jeuxRPG._class.res.team.team import Team

knight = Character.create("Knight", "0000000", "Bob")
bad_guy = Character.create("Knight", "1111111", "Bad Guy")

Team("Heroes", knight)
Team("Enemies", bad_guy)

battle = TeamBattle(knight.team, bad_guy.team)
battle.auto_battle()
🚀 Objectifs
Ce projet a été conçu dans un but d’apprentissage :

Structurer un projet Python modulaire

Approfondir la programmation orientée objet (POO)

Mettre en pratique des patterns simples (factory, gestion d’état…)

💡 Technologies utilisées
Python 3.x

python-dotenv

pydantic

▶️ Lancer le projet
Cloner le dépôt :

bash
Copier
Modifier
git clone https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
Installer les dépendances :

bash
Copier
Modifier
pip install -r requirements.txt
Lancer un test :

bash
Copier
Modifier
python test.py
👤 Auteur
Baptiste Da Silva
Étudiant en développement informatique
💼 En recherche d’alternance pour septembre 2025
🔗 linkedin.com/in/baptiste-da-silva-0374b6336

⭐ Remerciements
Si tu apprécies ce projet, n’hésite pas à me contacter ou à me donner des conseils !
Ce projet a pour vocation d’être intégré à un futur bot Discord.

---

## 🚦 Load testing (Locust)

Le dossier de tests de charge est dans `test/load`.

### Préparer l'environnement

```bash
python -m venv test/load/.venv
test/load/.venv/Scripts/python.exe -m pip install -U pip
test/load/.venv/Scripts/python.exe -m pip install locust
```

### Lancer un test en CLI

```bash
# 1) Démarrer un serveur HTTP local à la racine du projet
test/load/.venv/Scripts/python.exe -m http.server 8000

# 2) Dans un autre terminal, lancer Locust en headless
test/load/.venv/Scripts/locust.exe -f test/load/locustfile.py --headless -u 10 -r 2 -t 30s --host http://127.0.0.1:8000
```

Le `locustfile.py` couvre plusieurs pages (racine, README, requirements, docs, répertoire tests) et inclut un scénario `POST /formulaire`.

## Known issues

- Le projet n’expose pas encore une application web (pas de routes HTTP métier dédiées), donc la charge est mesurée via un serveur HTTP statique local.
- L’endpoint `POST /formulaire` n’existe pas côté application actuellement ; le scénario est conservé pour préparer l’arrivée de formulaires réels.
- Le README historique contient du formatage markdown partiellement incohérent (sections/code fences) qui mériterait un nettoyage dédié.
- Les optimisations de perf web (cache, pooling, endpoints dynamiques) ne sont pas encore applicables tant que l’API web n’est pas en place.