# RPG Python — POC multijoueur autonome

Un tutoriel RPG jouable seul ou en coopération à deux dans le navigateur, avec identités distinctes, invitations privées, état partagé et sauvegarde SQLite.

Le tutoriel utilise les cinq classes du moteur RPG et leurs compétences : attaques, soins, améliorations et invocations. Les compétences sont acquises aux niveaux définis dans les tables de chaque classe. Un duel simplifié reste disponible comme démonstration optionnelle.

## Démarrer en local

Python **3.11 ou plus récent** est requis. Aucun compte externe, bot Discord ou service de base de données n'est nécessaire.

```bash
git clone --branch codex/secure-multiplayer-poc https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
python main.py
```

Ouvrir **http://127.0.0.1:8080**. Tant que la pull request du POC n'est pas fusionnée, utiliser la branche `codex/secure-multiplayer-poc`.

1. Créer un personnage puis cliquer sur **Commencer le tutoriel en solo**.
2. Pour jouer à deux, cliquer plutôt sur **Inviter un compagnon**, partager l'invitation, puis démarrer le tutoriel du groupe une fois le compagnon arrivé. Ouvrir un nouvel onglet plutôt que dupliquer l'onglet existant, pour garder des identités distinctes.
3. Explorer la clairière, battre le premier gobelin avec une attaque simple ou une compétence, puis rejoindre Rosée.
4. Parler à Mira et battre trois gobelins. Chaque victoire apporte de l'expérience et des matériaux à chaque membre du groupe.
5. Rendre la quête : les personnages atteignent le niveau 5 et acquièrent les compétences correspondantes de leur classe. Un entraînement sans récompenses permet de les essayer.
6. À la forge, chaque joueur fabrique et équipe sa veste avec deux peaux et trois crocs. La veste donne 10 PV supplémentaires et 3 points d'endurance.
7. Une fois chaque aventurier équipé, rejoindre Brume pour terminer le tutoriel.

Les actions de combat sont espacées de trois secondes. L'attaque simple est gratuite ; les compétences dépensent l'énergie prévue par leur classe. Les compétences offensives visent le gobelin, les soins et améliorations un membre du groupe, et les invocations leur propriétaire. Le repos régénère l'énergie et réduit les délais exprimés en tours ; le gobelin peut riposter. Hors combat, le repos restaure complètement PV et énergie. Une victoire soigne le groupe. Une défaite collective permet de recommencer le combat sans perdre la quête ni le butin déjà acquis.

L'interface sépare exploration, dialogue PNJ, journal de quête, combat, forge et statistiques. Un seul écran de situation est affiché à la fois. Les statistiques donnent les PV, la force, l'endurance, l'intelligence, la sagesse, les énergies, les compétences, le sac et l'équipement. Le combat apparaît à la rencontre d'un ennemi ; les cibles sont absentes à l'apparition du personnage et hors combat.

En combat, choisir d'abord une cible : seules l'attaque simple et les compétences utilisables sur elle apparaissent. Un personnage à pleine vie n'est pas proposé pour un soin, une invocation doit viser son propriétaire et une attaque doit viser l'ennemi vivant du combat. Une cible sans action disponible est masquée, notamment pendant le délai global. Le client filtre les choix à partir de l'état reçu et des règles de ciblage ; le serveur recalcule les conditions lors de chaque commande. Les actions refusées ne consomment ni énergie ni objets.

Le monde possède un marchand itinérant entre Rosée et Brume. Son passage est déterminé par l'horloge interne au ratio 1:20, sans afficher le ratio ni le temps écoulé dans l'interface. Mira reste disponible pour éviter de bloquer le tutoriel. Le marchand est pour l'instant un PNJ de passage, sans boutique.

L'identité est conservée dans l'onglet pendant sa session. Pour retrouver un personnage après fermeture de l'onglet, conserver sa **clé de reconnexion** en privé et la saisir dans « Retrouver mon personnage ». Se déconnecter conserve la progression du tutoriel. En revenant avec sa clé, le joueur retrouve son groupe et ses compétences, son inventaire et son équipement.

Les données sont conservées dans `.data/multiplayer.sqlite3`. Redémarrer avec le même fichier restaure personnages, sessions, dégâts et commandes déjà exécutées. Le temps hors ligne est pris en compte pour les passages des PNJ. Le tutoriel n'expire pas et aucun dégât automatique n'est infligé pendant l'arrêt. Les anciens salons et duels conservent leurs échéances.

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
| `attack` | `session_id`, `revision`, et `target` optionnel pour les anciens clients |
| `leave` | `session_id`, `revision` |
| `tutorial` | Aucun ; démarre un tutoriel solo ou le salon du créateur |
| `explore`, `rest` | `session_id`, `revision` |
| `strike` | `session_id`, `revision`, `target` (`mob`) |
| `skill` | `session_id`, `revision`, `skill_name`, `target` |
| `talk` | `session_id`, `revision`, `npc` (`mira`) |
| `craft` | `session_id`, `revision`, `recipe` (`veste`) |
| `travel` | `session_id`, `revision`, `destination` (`rosee`, `brume`) |

Le bot doit afficher les résultats, désactiver les mentions, répondre aux interactions et organiser ses notifications. Le SDK, le token Discord et les commandes slash ne sont pas inclus dans ce POC. Pour piloter l'expiration hors requêtes, le bot peut appeler `service.tick()` régulièrement depuis un thread ou une tâche asynchrone. L'adaptateur réutilise l'identifiant d'interaction pour empêcher une exécution en double.

## Fonctionnement et limites

- SQLite applique les mutations et leurs reçus de commande dans une transaction unique. Une version d'état obsolète est refusée avec `stale_revision` ; actualiser avant une nouvelle action.
- Une commande rejouée avec le même identifiant et le même contenu retourne son résultat initial. Un contenu différent avec cet identifiant est refusé. Les identifiants et reçus sont persistés.
- L'horloge utilise le temps monotone pendant l'exécution et un checkpoint persistant pour la reprise. Le serveur réconcilie les échéances toutes les 100 ms ; l'interface interroge l'état toutes les 500 ms. Ce n'est pas un système temps réel dur.
- Un personnage ne peut participer qu'à une session active à la fois. Le tutoriel suit un parcours partagé et guidé, avec des sacs et équipements individuels. Les combats sont des échanges action/riposte avec un délai serveur ; les ennemis n'attaquent pas les joueurs déconnectés. Le monde ouvert, les échanges, les boutiques et les quêtes génériques ne sont pas encore implémentés.
- La clé personnelle est un secret d'accès, pas une authentification par mot de passe ou OAuth. Aucune récupération par email ni révocation de compte n'est fournie. Le POC est destiné à un environnement de démonstration contrôlé.
- La nouvelle table des tutoriels est créée automatiquement sans modifier les données des anciens duels. Sauvegarder la base après arrêt du serveur avant une mise à jour. Un nouveau tutoriel recommence au niveau 1 ; la progression reste attachée à son aventure sauvegardée.

## Organisation

| Répertoire | Rôle |
| --- | --- |
| `multiplayer/` | Horloge PNJ, tutoriel, service transactionnel, serveur HTTP et adaptateur Discord |
| `multiplayer/web/` | Interface navigateur autonome en français |
| `_class/`, `_core/`, `game_engine/` | Moteur RPG historique et sauvegardes sécurisées |
| `test/` | Tests du moteur et du POC |

Les anciennes sauvegardes JSON restent accessibles au moteur historique, mais ne sont pas importées automatiquement dans le POC SQLite. Les identifiants invalides sont maintenant rejetés, plutôt que transformés silencieusement en noms de fichiers susceptibles de se collisionner.
