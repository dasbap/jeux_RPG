# 🧙‍♂️ RPG Python – Projet personnel

Ce projet est un prototype de jeu de rôle (RPG) textuel développé en Python. Il intègre un système de combat en équipe, des classes de personnages, un système de progression, et des compétences.

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
- `test/` : tests unitaires et d’intégration

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
```

## 🚀 Objectifs

- Structurer un projet Python modulaire
- Approfondir la programmation orientée objet (POO)
- Mettre en pratique des patterns simples (factory, gestion d’état…)

## 💡 Technologies

- Python 3.x
- python-dotenv
- pydantic

## ▶️ Installation

1. Cloner le dépôt :

```bash
git clone https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
```

2. Installer les dépendances :

```bash
pip install -r requirements.txt
```

3. Lancer un test simple :

```bash
python test.py
```

## 🚦 Tests de charge (Locust)

Le projet contient une configuration de tests de charge sous `test/load`. Pour les détails et les commandes exactes exécutées, voir le fichier `ACTIONS_PERFORMED.md` à la racine du projet.

## Known issues

- Le projet n’expose pas encore d’API web métier ; les tests de charge utilisent un serveur HTTP statique pour mesurer la capacité de servir des fichiers.
- Le scénario `POST /formulaire` est présent dans les tests de charge mais l’endpoint n’existe pas côté application.
- Le README historique contenait des incohérences de formatage ; il a été nettoyé.

## Historique

- v1.0 — Ajout du prototype de jeu, tests unitaires initiaux.
- v1.1 — Ajout de tests de charge et documentation des étapes d’installation (voir `ACTIONS_PERFORMED.md`).

---

