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
3. Ouvrir **Carte**, explorer le lieu actuel ou sélectionner **Sous-bois**, puis **Se déplacer à ce point**. Battre le premier gobelin, puis prendre le chemin de Rosée depuis la carte.
4. Dans les détails de Rosée sur la carte, cliquer sur l’icône de la **Place du village · Mira**. La marche locale commence et les actions de Mira apparaissent à votre arrivée. Accepter la quête et explorer le campement de la lisière pour battre trois gobelins. Chaque victoire apporte de l’expérience. Approchez les corps pour les dépecer et partager les matériaux, puis quittez explicitement le champ de bataille.
5. Rendre la quête : la récompense contribue à la progression ; les compétences restent héritées de la classe et débloquées aux niveaux prévus. Un entraînement sans récompenses permet de les essayer.
6. À la forge, chaque joueur fabrique et équipe sa veste avec deux peaux et trois crocs. La veste donne 10 PV supplémentaires et 3 points d'endurance.
7. Une fois chaque aventurier équipé, rejoindre Brume pour terminer le tutoriel.

Les actions de combat sont espacées de **1,2 seconde réelle**. Chaque compétence garde son propre délai, mesuré dans le temps : une compétence n’empêche pas une attaque simple dès la fin du délai global. Le Slash du chevalier coûte **10 Aura** ; les autres coûts sont augmentés, sans dépasser la réserve maximale de la classe. L’énergie revient progressivement, indépendamment des commandes, sans remboursement après une attaque ou une victoire. L’attaque simple et les compétences évoluent avec les caractéristiques, avec un coefficient réduit pour l’attaque simple du chevalier. Une défaite collective secourt le groupe sans supprimer sa quête ni les matériaux déjà récupérés.

La carte horizontale reste visible au-dessus de trois panneaux indépendants : consultation (caractéristiques, inventaire, équipement et bestiaire), actions du lieu actuel (exploration, dialogue, fabrication ou combat) et journal de quêtes. Changer d'onglet de consultation conserve les actions et les quêtes visibles. Sur un écran étroit, les panneaux se réorganisent pour rester lisibles. Cliquer sur une icône dans la zone actuelle rejoint directement ce point. Les icônes des autres zones ouvrent leurs détails et chemins connus. Pendant la marche, les interactions sont bloquées. En combat, la carte devient un champ de bataille ; les autres panneaux disparaissent, seuls les déplacements tactiques sont autorisés. Le détail des lieux reste fermé jusqu’à un clic. Localiser une quête dessine un cercle creux sans changer la zone consultée, même si la destination reste à découvrir. Un déplacement vers une autre zone demande une confirmation côté client. La forge affiche explicitement son verrouillage jusqu’à la remise de la quête de Mira. Les interactions avec Mira ou la forge demandent de rejoindre physiquement leur point ; le serveur refuse les actions à distance. Léon est accessible depuis son icône uniquement lorsqu’il est présent dans la zone actuelle.

En combat, choisir d'abord une cible : seules l'attaque simple et les compétences utilisables sur elle apparaissent. Un allié n'est proposé que si une compétence de soin ou de buff acquise permet une action sur lui. Un personnage à pleine vie n'est pas proposé pour un soin, une invocation doit viser son propriétaire et une attaque doit viser l'ennemi vivant du combat. Une cible sans action disponible est masquée, notamment pendant le délai global. Le client filtre les choix à partir de l'état reçu et des règles de ciblage ; le serveur recalcule les conditions lors de chaque commande. Les actions refusées ne consomment ni énergie ni objets.

Le monde possède un marchand itinérant entre Rosée et Brume. Son passage est déterminé par l'horloge interne au ratio 1:3, sans afficher le ratio ni le temps écoulé dans l'interface. Mira reste disponible pour éviter de bloquer le tutoriel. Léon reste huit heures de jeu dans chaque village (160 minutes réelles), puis marche jusqu’au suivant. Pendant sa traversée, il n’est présent dans aucun village. Il est pour l’instant un PNJ de passage, sans boutique.

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
| `craft`, `upgrade` | `session_id`, `revision`, `recipe` (`casque`, `veste`, `gants`, `jambieres`, `bottes`, `ceinture`) |
| `battle_move` | `session_id`, `revision`, `x`, `y`, `path` (cases adjacentes) |
| `hide`, `leave_battle` | `session_id`, `revision` |
| `harvest` | `session_id`, `revision`, `target` (identifiant du corps) |
| `travel` | `session_id`, `revision`, `destination` (`rosee`, `brume`) |

Le bot doit afficher les résultats, désactiver les mentions, répondre aux interactions et organiser ses notifications. Le SDK, le token Discord et les commandes slash ne sont pas inclus dans ce POC. Pour piloter l'expiration hors requêtes, le bot peut appeler `service.tick()` régulièrement depuis un thread ou une tâche asynchrone. L'adaptateur réutilise l'identifiant d'interaction pour empêcher une exécution en double.

## Fonctionnement et limites

- SQLite applique les mutations et leurs reçus de commande dans une transaction unique. Une version d'état obsolète est refusée avec `stale_revision` ; actualiser avant une nouvelle action.
- Une commande rejouée avec le même identifiant et le même contenu retourne son résultat initial. Un contenu différent avec cet identifiant est refusé. Les identifiants et reçus sont persistés.
- L'horloge utilise le temps monotone pendant l'exécution et un checkpoint persistant pour la reprise. Le serveur réconcilie les échéances toutes les 100 ms ; l'interface interroge l'état toutes les 500 ms. Ce n'est pas un système temps réel dur.
- Un personnage ne peut participer qu'à une session active à la fois. Le tutoriel suit un parcours partagé et guidé, avec des sacs et équipements individuels. Les combats évoluent dans la boucle autonome du serveur, avec des positions individuelles ; quitter l’onglet ne met pas un combat en pause. Le monde ouvert, les échanges, les boutiques et les quêtes génériques ne sont pas encore implémentés.
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

## Carte et bestiaire

La carte affiche les lieux et chemins connus dans le parcours du tutoriel. Les lieux connus mais non visités restent sans détails ni points stratégiques. Les descriptions et points des villages déjà visités restent consultables, même après le départ. Les points incluent la place de Mira, la forge, le terrain d'entraînement et les rencontres de la clairière et de la lisière. Les routes ne permettent de voyager que lorsque les conditions du parcours sont satisfaites. La carte reste consultable pendant un combat, avec les interactions de voyage et des points désactivées. Le passage du marchand itinérant est indiqué dans les villages visités où il est présent.

Le bestiaire ne révèle que les monstres rencontrés. Le tutoriel contient actuellement le gobelin des bois : sa fiche donne les PV des rencontres, caractéristiques, matériaux et quantités, expérience, lieux observés, faiblesses et résistances. Le gobelin actuel n'a aucune faiblesse ni résistance particulière définie. Les PV, matériaux et récompenses utilisent les mêmes règles que les combats. Les découvertes sont partagées dans le groupe, sauvegardées avec l'aventure et compatibles avec les sauvegardes antérieures, sans suppression des données.


## Déplacements et groupes de créatures

La position du groupe est sauvegardée. « Vous êtes ici » indique sa zone sur la carte et son point précis dans le panneau des actions. `move` accepte un identifiant de zone ou de point connu ; le serveur calcule le trajet sur le graphe des chemins. La marche est chronométrée côté serveur selon la distance et une vitesse de 6 km/h dans le monde. La position progresse sur la carte pendant le trajet. Un point de contrôle de rencontre est effectué au plus tous les 250 mètres des segments dangereux, avec un contrôle en fin de segment. Plusieurs contrôles peuvent donc avoir lieu sur un même chemin. Les portions locales mesurent 10 mètres. Un combat suspend le trajet ; sa sortie explicite après la victoire relance les étapes restantes. Plusieurs combats peuvent donc survenir pendant un seul déplacement. Une défaite annule le trajet et ramène le groupe dans un lieu sûr. La position est commune aux deux joueurs de ce POC coopératif.

Le calcul des groupes est commun aux rangs S, A, B, C, D et E et s'arrête au premier échec, avec cinq créatures maximum. À niveaux égaux, les gobelins de rang D utilisent les probabilités conditionnelles suivantes :

| Créature | Probabilité si toutes les précédentes sont apparues |
| --- | --- |
| 1 | 90 % |
| 2 | 30 % |
| 3 | 10 % |
| 4 | 3 % |
| 5 | 0,1 % |

Ainsi, rencontrer au moins deux gobelins a une probabilité de 90 % × 30 % = 27 %. Ces probabilités ne sont pas des poids pour choisir directement une taille de groupe. Le niveau de zone comparé au niveau du membre le moins avancé multiplie les seuils par `2 ** ((niveau_zone - niveau_joueur) / 5)`, borné entre 0,25 et 1,5. Chaque seuil final est limité à 100 %. Les rangs plus difficiles réduisent les probabilités d'ajouter des créatures, selon un diviseur croissant ; leur premier seuil de base vaut 100 %. Le rang E est passif et ne déclenche aucun combat hostile. Les lapins et cerfs ne sont pas encore ajoutés. Les coefficients des rangs S à C constituent un premier équilibrage configurable dans `multiplayer/encounters.py`.

Chaque ennemi possède un identifiant de cible et sa propre prochaine attaque. Les attaques autonomes sont traitées par le serveur, même sans commande du joueur. Après une interruption du serveur, une seule attaque par ennemi est exécutée à la reprise, sans rafale de rattrapage. La révision, les droits de session, la présence du joueur et la validité de la cible restent vérifiés transactionnellement.


Les chemins actuels ont des distances de démonstration, configurées dans `multiplayer/world.py` :

| Chemin | Distance | Marche réelle sans combat au ratio 1:3 |
| --- | --- | --- |
| Clairière → Rosée | 0,3 km | 60 s |
| Rosée → Lisière | 0,2 km | 40 s |
| Rosée → Brume | 1 km | 200 s |

Un combat gèle la marche restante. Sa durée s’ajoute au trajet ; quitter le champ de bataille relance les portions restantes. Les échéances et la distance restante sont sauvegardées, et un trajet déjà engagé ne peut pas être remplacé par une autre commande de déplacement. L’arrivée à Brume termine le tutoriel via la boucle autonome du serveur.

Une rencontre tire le groupe entier avant le début du combat : si trois gobelins sont tirés, ils sont tous présents simultanément, ciblables séparément et autonomes. L’interface indique le numéro de rencontre et le nombre d’ennemis vivants par rapport au groupe initial. Un long trajet peut ensuite déclencher d’autres rencontres, chacune avec son propre groupe.


## Combat tactique et progression du POC 0.8

Quinze presets sont disponibles : trois terrains pour chacun des cinq contextes (clairière, lisière, route, entraînement à Rosée et bois de Brume). Une case représente deux mètres. Le joueur marche à 6 km/h et le gobelin se déplace à 3 km/h en combat (respectivement 1,2 et 2,4 secondes de jeu par case). Les couvertures bloquent la marche et la ligne de vue. Le corps à corps porte à 1,5 case ; les classes à distance et les compétences de soutien portent à six cases. L’interface affiche chaque mob, ses PV sous forme de barre, sa position et son intention. Cliquer sur sa fiche PV entoure sa position.

Explorer donne l’initiative : les joueurs apparaissent dissimulés et les mobs patrouillent. Un joueur visible et atteignable est poursuivi ; chaque membre du groupe garde son propre placement et sa dissimulation. Perdre un joueur de vue déclenche une recherche à sa dernière position connue, pendant 30 secondes de jeu (10 secondes réelles), puis la patrouille reprend. Un stun bloque déplacement, attaque et appel ; sans cible visible à son réveil, le mob reprend sa patrouille.

Un mob qui repère un ennemi, subit une première attaque ou voit l’ennemi s’éloigner peut appeler ses alliés. L’appel dure six secondes de jeu (deux réelles), comme son délai de réutilisation. Les dégâts ou un stun l’interrompent. Un allié mort reste considéré comme joignable tant que son corps n’a pas été vu. Les autres mobs reçoivent une dernière position connue, sans révélation magique d’un joueur caché.

La victoire conserve les corps et le champ de bataille. Il faut approcher à 1,5 case pour dépecer ; chaque corps ne rapporte qu’une fois ses matériaux, partagés avec le groupe. Sortir abandonne les corps non dépecés et reprend le voyage suspendu. L’entraînement ne rapporte ni expérience ni matériaux.

La forge fabrique casque, torse, gants, jambières, bottes et ceinture. Chaque pièce possède son niveau indépendant de +0 à +10 et ses bonus de PV/endurance. Les coûts communs suivent `quantité_initiale × (niveau + 1) + niveau²`. Dès +4, il faut des cristaux de gobelin (8 % de chance par corps) ; dès +8, des noyaux (2 %). Ces quantités augmentent avec le niveau. À +10, les noms ajoutent respectivement **raffiné**, **solide**, **précis**, **robustes**, **agiles**, **renforcée**. Une amélioration refusée ne retire aucun matériau et n’ajoute aucun bonus.

Un gobelin rapporte 50 XP par joueur. Le prochain niveau nécessite `500 × niveau^1,8` XP, arrondies à l’entier inférieur : 500 au niveau 1, 1 741 au niveau 2, puis des seuils croissants. Les anciens personnages conservent leur niveau et leur équipement lors de la migration.

Le client calcule les chemins tactiques, les possibilités de ciblage et le rendu. Le serveur contrôle session, révision, délais, ressources, cases adjacentes, portée et ligne de vue ; il conserve l’autorité sur les dégâts, récompenses, IA et déplacements des PNJ. Il ne fait pas confiance à un dommage ou à un déplacement instantané annoncé par un client. Les modèles de personnages reconstruits sont mis en cache pour limiter le coût des instantanés. Le bestiaire filtre les cartes de spawn effectivement découvertes et les noms/matériaux ; le tri des cartes n’apparaît que lorsqu’au moins deux sont connues.

Les contrôles de rencontre sont placés à un premier instant aléatoire dans chaque segment, puis au plus tous les 250 mètres. Un combat peut donc commencer au début, au milieu ou à la fin d’un trajet. Le monde reste un POC coopératif limité à deux joueurs et au gobelin comme espèce hostile ; les probabilités, statistiques et terrains restent des premiers réglages à équilibrer en jeu.

Pour reproduire le parcours HTTP de deux clients avec un DOM jsdom (Node.js requis), après installation du paquet Python :

```bash
npm install --prefix .ui-test jsdom@26.1.0
python scripts/verify_http_ui.py
```

Ce script démarre un serveur de test local avec une base temporaire, une horloge accélérée et des tirages déterministes. Il accélère aussi la fenêtre du limiteur de requêtes pour suivre l’horloge du scénario. Les protections HTTP avec leurs limites réelles et les délais du jeu sont testés séparément par `python -m pytest -q`. Le scénario jsdom vérifie les comportements et le DOM ; il ne constitue pas une vérification visuelle dans un navigateur.

La CI exécute également le scénario HTTP/jsdom. Il vérifie explicitement qu’après la mort du dernier ennemi, les anciennes fiches PV et intentions disparaissent, qu’un clic permet encore de marcher jusqu’au corps et que le bouton de sortie termine effectivement le combat après dépeçage.
