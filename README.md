# RPG Python — POC multijoueur autonome

Un duel à deux joueurs dans le navigateur, avec identités distinctes, invitations privées, état partagé et sauvegarde SQLite. Le serveur calcule les actions et le temps : **1 seconde réelle = 20 secondes de jeu**.

Le moteur RPG historique est conservé. Le POC réutilise ses cinq classes jouables pour créer les personnages et applique des règles de duel simples, séparées des combats historiques par tours.

## Démarrer en local

Python **3.11 ou plus récent** est requis. Aucun compte externe, bot Discord ou service de base de données n'est nécessaire.

```bash
git clone https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
python main.py
```

Ouvrir **http://127.0.0.1:8080**. Tant que la pull request du POC n'est pas fusionnée, utiliser la branche `codex/secure-multiplayer-poc`.

1. Créer un personnage dans un premier onglet.
2. Cliquer sur **Créer un salon** et copier l'invitation.
3. Ouvrir manuellement un nouvel onglet à la même adresse, créer un second personnage et rejoindre avec l'invitation. Éviter « Dupliquer l'onglet », qui peut recopier son identité. Un autre navigateur convient également.
4. Le créateur démarre le duel lorsque les deux joueurs sont présents.
5. Chaque joueur peut attaquer toutes les **3 secondes réelles**, soit 60 secondes de jeu. Les points de vie et le journal se mettent à jour automatiquement.
6. Le duel se termine à la défaite d'un joueur, à l'abandon ou après 5 minutes réelles. Un salon en attente expire après 10 minutes réelles.

L'identité est conservée dans l'onglet pendant sa session. Pour retrouver un personnage après fermeture de l'onglet, conserver sa **clé de reconnexion** en privé et la saisir dans « Retrouver mon personnage ». Se déconnecter ne quitte pas automatiquement un duel : utiliser **Quitter la session** avant de se déconnecter si nécessaire.

Les données sont conservées dans `.data/multiplayer.sqlite3`. Redémarrer avec le même fichier restaure personnages, sessions, dégâts et commandes déjà exécutées. Le temps hors ligne est pris en compte ; aucun dégât automatique n'est infligé pendant l'arrêt, mais les sessions peuvent expirer.

```bash
python main.py --port 8090 --database .data/mon-monde.sqlite3
```

## Installation du paquet et tests

Le paquet est installable sous le nom `jeux-rpg`, avec les imports Python `jeuxRPG`. Le lancement depuis les sources fonctionne aussi sans installation du paquet.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install '.[test]'
jeux-rpg --port 8080
```

Sous Windows, activer l'environnement avec `.venv\Scripts\activate`.

```bash
python -m pytest -q
```

Les tests couvrent notamment le parcours HTTP à deux joueurs, les actions concurrentes, le contrôle de propriété, les invitations, la reprise, la déduplication des commandes, le ratio temporel et les chemins de sauvegarde. Six tests sont explicitement ignorés quand les fonctionnalités de carte mises en pause et le module de bot externe ne sont pas disponibles.

Pour vérifier également les interactions de l'interface, démarrer le serveur dans un terminal, puis exécuter dans un second terminal avec Node.js 22 ou plus récent :

```bash
npm install --prefix .ui-test --no-audit --no-fund jsdom@26.1.0
NODE_PATH="$PWD/.ui-test/node_modules" node scripts/verify_ui.cjs
```

Ce test crée deux personnages de démonstration. Il exécute le JavaScript de l'interface dans jsdom contre le vrai serveur HTTP ; il vérifie le parcours fonctionnel et le rendu sûr du texte utilisateur, mais ne remplace pas un contrôle visuel dans un navigateur réel.

La configuration Locust historique teste un serveur statique ; elle ne constitue pas une mesure de capacité du POC. Les limites du serveur sont indiquées dans [SECURITY.md](SECURITY.md).

## Jouer à distance

Le serveur écoute uniquement sur **127.0.0.1**. Pour jouer depuis deux machines, installer un reverse proxy HTTPS sur la même machine que le moteur, puis déclarer son origine exacte :

```bash
jeux-rpg --public-origin https://rpg.example.com
```

Exemple de `Caddyfile` à adapter à un domaine que vous contrôlez :

```caddyfile
rpg.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Le proxy doit transmettre le `Host` public, laisser passer `Authorization` et désactiver toute mise en cache des réponses. L'application n'accorde aucun accès CORS et ne fait pas confiance aux en-têtes d'adresse client du proxy. Les limites par adresse IP seront donc partagées derrière ce proxy. La configuration HTTPS est fournie comme exemple ; aucun hébergement distant n'est créé automatiquement.

## Entrées réutilisables par un bot Discord

`multiplayer/discord_adapter.py` expose une interface asynchrone indépendante du SDK Discord. Elle reçoit l'objet d'interaction **issu du SDK côté serveur** ; `guild_id`, `user.id` et `interaction.id` ne doivent jamais provenir de paramètres saisis par le joueur. Les personnages et invitations sont isolés par serveur Discord et du monde web local.

```python
from jeuxRPG.multiplayer import GameService
from jeuxRPG.multiplayer.discord_adapter import DiscordAdapter

service = GameService(".data/discord.sqlite3")
adapter = DiscordAdapter(service)
result = await adapter.execute(interaction, "create", class_name="Knight")
```

Actions prises en charge :

| Action | Paramètres |
| --- | --- |
| `state` | Aucun, ou `session_id` |
| `create` | Aucun |
| `join` | `invite` |
| `start` | `session_id`, `revision` |
| `attack` | `session_id`, `revision` |
| `leave` | `session_id`, `revision` |

Le bot doit afficher les résultats, désactiver les mentions, répondre aux interactions et organiser ses notifications. Le SDK, le token Discord et les commandes slash ne sont pas inclus dans ce POC. Pour piloter l'expiration hors requêtes, le bot peut appeler `service.tick()` régulièrement depuis un thread ou une tâche asynchrone. L'adaptateur réutilise l'identifiant d'interaction pour empêcher une exécution en double.

## Fonctionnement et limites

- SQLite applique les mutations et leurs reçus de commande dans une transaction unique. Une version d'état obsolète est refusée avec `stale_revision` ; actualiser avant une nouvelle action.
- Une commande rejouée avec le même identifiant et le même contenu retourne son résultat initial. Un contenu différent avec cet identifiant est refusé. Les identifiants et reçus sont persistés.
- L'horloge utilise le temps monotone pendant l'exécution et un checkpoint persistant pour la reprise. Le serveur réconcilie les échéances toutes les 100 ms ; l'interface interroge l'état toutes les 500 ms. Ce n'est pas un système temps réel dur.
- Un personnage ne peut participer qu'à une session active à la fois. Le POC est un duel PvP à deux joueurs : les compétences complètes, les combats coopératifs, la navigation partagée, les quêtes et l'économie ne sont pas branchés dans cette interface.
- La clé personnelle est un secret d'accès, pas une authentification par mot de passe ou OAuth. Aucune récupération par email ni révocation de compte n'est fournie. Le POC est destiné à un environnement de démonstration contrôlé.
- Le fichier SQLite utilise un schéma de POC initial ; il n'existe pas encore de mécanisme de migration pour de futures versions. Sauvegarder la base après arrêt du serveur avant une mise à jour.

## Organisation

| Répertoire | Rôle |
| --- | --- |
| `multiplayer/` | Horloge, service transactionnel, serveur HTTP et adaptateur Discord |
| `multiplayer/web/` | Interface navigateur autonome en français |
| `_class/`, `_core/`, `game_engine/` | Moteur RPG historique et sauvegardes sécurisées |
| `test/` | Tests du moteur et du POC |

Les anciennes sauvegardes JSON restent accessibles au moteur historique, mais ne sont pas importées automatiquement dans le POC SQLite. Les identifiants invalides sont maintenant rejetés, plutôt que transformés silencieusement en noms de fichiers susceptibles de se collisionner.
