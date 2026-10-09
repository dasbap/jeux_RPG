# RPG Python — Alpha multijoueur autonome

Un tutoriel RPG jouable seul ou en coopération à deux dans le navigateur, avec identités distinctes, invitations privées, état partagé et sauvegarde SQLite.

Le tutoriel utilise les cinq classes du moteur RPG et leurs compétences : attaques, soins, améliorations et invocations. Les compétences sont acquises aux niveaux définis dans les tables de chaque classe. Un duel simplifié reste disponible comme démonstration optionnelle.

## Démarrer en local

Python **3.11 ou plus récent** est requis. Aucun compte externe, bot Discord ou service de base de données n'est nécessaire.

```bash
git clone https://github.com/dasbap/jeux_RPG.git
cd jeux_RPG
python main.py
```

Ouvrir **http://127.0.0.1:8080**.

1. Créer un personnage puis cliquer sur **Commencer le tutoriel en solo**.
2. Pour jouer à deux, cliquer plutôt sur **Inviter un compagnon**, partager l'invitation, puis démarrer le tutoriel du groupe une fois le compagnon arrivé. Ouvrir un nouvel onglet plutôt que dupliquer l'onglet existant, pour garder des identités distinctes.
3. Ouvrir **Carte**, explorer le lieu actuel ou sélectionner **Sous-bois**, puis **Se déplacer à ce point**. Battre le premier gobelin, puis prendre le chemin de Rosée depuis la carte.
4. Dans les détails de Rosée sur la carte, cliquer sur l’icône de la **Place du village · Mira**. La marche locale commence et les actions de Mira apparaissent à votre arrivée. Accepter la quête et explorer le campement de la lisière pour battre trois gobelins. Chaque victoire apporte de l’expérience. Approchez les corps pour les dépecer et partager les matériaux, puis quittez explicitement le champ de bataille.
5. Rendre la quête : la récompense contribue à la progression ; les compétences restent héritées de la classe et débloquées aux niveaux prévus. Un entraînement sans récompenses permet de les essayer.
6. À la forge, chaque joueur fabrique et équipe sa veste avec deux peaux et trois crocs. La veste donne 10 PV supplémentaires et 3 points d'endurance.
7. Une fois chaque aventurier équipé, rejoindre Brume pour terminer le tutoriel.

Les actions de combat sont espacées de **1,2 seconde réelle**. Chaque compétence garde son propre délai, mesuré dans le temps : une compétence n’empêche pas une attaque simple dès la fin du délai global. Le Slash du chevalier coûte **10 Aura** ; les autres coûts sont augmentés, sans dépasser la réserve maximale de la classe. L’énergie revient progressivement, indépendamment des commandes, sans remboursement après une attaque ou une victoire. L’attaque simple et les compétences évoluent avec les caractéristiques, avec un coefficient réduit pour l’attaque simple du chevalier. Une défaite collective secourt le groupe sans supprimer sa quête ni les matériaux déjà récupérés.

La carte horizontale reste visible au-dessus de trois panneaux indépendants : consultation (caractéristiques, inventaire, équipement et bestiaire), actions du lieu actuel (exploration, dialogue, fabrication ou combat) et journal de quêtes. Changer d'onglet de consultation conserve les actions et les quêtes visibles. Sur un écran étroit, les panneaux se réorganisent pour rester lisibles. Cliquer sur une icône dans la zone actuelle rejoint directement ce point. Les icônes des autres zones ouvrent leurs détails et chemins connus. Pendant la marche, les interactions sont bloquées. En combat, les actions et ressources du joueur apparaissent à gauche, la carte du champ de bataille au centre et les mobs avec leurs PV et intentions à droite. Sur petit écran, ces panneaux sont empilés. Les autres panneaux disparaissent, seuls les déplacements tactiques sont autorisés. Le détail des lieux reste fermé jusqu’à un clic. Localiser une quête dessine un cercle creux sans changer la zone consultée, même si la destination reste à découvrir. Un déplacement vers une autre zone demande une confirmation côté client. La forge affiche explicitement son verrouillage jusqu’à la remise de la quête de Mira. Les interactions avec Mira ou la forge demandent de rejoindre physiquement leur point ; le serveur refuse les actions à distance. Léon est accessible depuis son icône uniquement lorsqu’il est présent dans la zone actuelle.

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

`jeuxRPG/multiplayer/discord_adapter.py` expose une interface asynchrone indépendante du SDK Discord. Elle reçoit l'objet d'interaction **issu du SDK côté serveur** ; `guild_id`, `user.id` et `interaction.id` ne doivent jamais provenir de paramètres saisis par le joueur. Les personnages et invitations sont isolés par serveur Discord et du monde web local.

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

- SQLite applique les mutations et leurs reçus de commande dans une transaction unique. Une révision cliente ancienne n'annule pas automatiquement une commande : le serveur recharge l'état courant et revalide les préconditions métier. Une révision future reste refusée avec `stale_revision`, et un identifiant explicite d'ancien combat reste refusé avec `stale_encounter`.
- Une commande rejouée avec le même identifiant et le même contenu retourne son résultat initial. Un contenu différent avec cet identifiant est refusé. Les identifiants et reçus sont persistés.
- L'horloge utilise le temps monotone pendant l'exécution et un checkpoint persistant pour la reprise. Le serveur réconcilie les échéances toutes les 100 ms ; l'interface interroge l'état toutes les 500 ms. Ce n'est pas un système temps réel dur.
- Un personnage ne peut participer qu'à une session active à la fois. Le tutoriel suit un parcours partagé et guidé, avec des sacs et équipements individuels. Les combats évoluent dans la boucle autonome du serveur, avec des positions individuelles ; quitter l’onglet ne met pas un combat en pause. Le monde ouvert, les échanges, les boutiques et les quêtes génériques ne sont pas encore implémentés.
- La clé personnelle est un secret d'accès, pas une authentification par mot de passe ou OAuth. Aucune récupération par email ni révocation de compte n'est fournie. Le POC est destiné à un environnement de démonstration contrôlé.
- La nouvelle table des tutoriels est créée automatiquement sans modifier les données des anciens duels. Sauvegarder la base après arrêt du serveur avant une mise à jour. Un nouveau tutoriel recommence au niveau 1 ; la progression reste attachée à son aventure sauvegardée.

## Organisation

| Répertoire | Rôle |
| --- | --- |
| `jeuxRPG/multiplayer/` | Horloge PNJ, tutoriel, service transactionnel, serveur HTTP et adaptateur Discord |
| `jeuxRPG/multiplayer/web/` | Interface navigateur autonome en français |
| `jeuxRPG/_class/`, `jeuxRPG/_core/`, `jeuxRPG/game_engine/` | Moteur RPG historique et sauvegardes sécurisées |
| `test/` | Tests du moteur et du POC |

Les anciennes sauvegardes JSON restent accessibles au moteur historique, mais ne sont pas importées automatiquement dans le POC SQLite. Les identifiants invalides sont maintenant rejetés, plutôt que transformés silencieusement en noms de fichiers susceptibles de se collisionner.

## Carte et bestiaire

La carte affiche les lieux et chemins connus dans le parcours du tutoriel. Les lieux connus mais non visités restent sans détails ni points stratégiques. Les descriptions et points des villages déjà visités restent consultables, même après le départ. Les points incluent la place de Mira, la forge, le terrain d'entraînement et les rencontres de la clairière et de la lisière. Les routes ne permettent de voyager que lorsque les conditions du parcours sont satisfaites. La carte reste consultable pendant un combat, avec les interactions de voyage et des points désactivées. Le passage du marchand itinérant est indiqué dans les villages visités où il est présent.

Le bestiaire ne révèle que les monstres rencontrés. Le tutoriel contient actuellement le gobelin des bois : sa fiche donne les PV des rencontres, caractéristiques, matériaux et quantités, expérience, lieux observés, faiblesses et résistances. Le gobelin actuel n'a aucune faiblesse ni résistance particulière définie. Les PV, matériaux et récompenses utilisent les mêmes règles que les combats. Les découvertes sont partagées dans le groupe, sauvegardées avec l'aventure et compatibles avec les sauvegardes antérieures, sans suppression des données.


## Déplacements et groupes de créatures

La position du groupe est sauvegardée. « Vous êtes ici » indique sa zone sur la carte et son point précis dans le panneau des actions. `move` accepte un identifiant de zone ou de point connu ; le serveur calcule le trajet sur le graphe des chemins. La marche est chronométrée côté serveur selon la distance et une vitesse de 6 km/h dans le monde. La position progresse sur la carte pendant le trajet. Un point de contrôle de rencontre est effectué au plus tous les 250 mètres des segments dangereux, avec un contrôle en fin de segment. Plusieurs contrôles peuvent donc avoir lieu sur un même chemin. Les portions locales mesurent 10 mètres. Un combat suspend le trajet ; sa sortie explicite après la victoire relance les étapes restantes. Plusieurs combats peuvent donc survenir pendant un seul déplacement. Une défaite annule le trajet et ramène le groupe dans un lieu sûr. La position est commune aux deux joueurs de ce POC coopératif.

Le calcul des groupes est commun aux rangs SSS, SS, S, AA, A, B, C, D et E et s'arrête au premier échec, avec cinq créatures maximum. À niveaux égaux, les gobelins de rang D utilisent les probabilités conditionnelles suivantes :

| Créature | Probabilité si toutes les précédentes sont apparues |
| --- | --- |
| 1 | 90 % |
| 2 | 30 % |
| 3 | 10 % |
| 4 | 3 % |
| 5 | 0,1 % |

Ainsi, rencontrer au moins deux gobelins a une probabilité de 90 % × 30 % = 27 %. Ces probabilités ne sont pas des poids pour choisir directement une taille de groupe. Le niveau de zone comparé au niveau du membre le moins avancé multiplie les seuils par `2 ** ((niveau_zone - niveau_joueur) / 5)`, borné entre 0,25 et 1,5. Chaque seuil final est limité à 100 %. Les rangs plus difficiles réduisent les probabilités d'ajouter des créatures, selon un diviseur croissant ; leur premier seuil de base vaut 100 %. Le rang E est passif et ne déclenche aucun combat hostile. Les lapins et cerfs ne sont pas encore ajoutés. Les coefficients des rangs SSS à C constituent un premier équilibrage configurable dans `jeuxRPG/multiplayer/encounters.py`.

Chaque ennemi possède un identifiant de cible et sa propre prochaine attaque. Les attaques autonomes sont traitées par le serveur, même sans commande du joueur. Après une interruption du serveur, une seule attaque par ennemi est exécutée à la reprise, sans rafale de rattrapage. La révision, les droits de session, la présence du joueur et la validité de la cible restent vérifiés transactionnellement.


Les chemins actuels ont des distances de démonstration, configurées dans `jeuxRPG/multiplayer/world.py` :

| Chemin | Distance | Marche réelle sans combat au ratio 1:3 |
| --- | --- | --- |
| Clairière → Rosée | 0,3 km | 60 s |
| Rosée → Lisière | 0,2 km | 40 s |
| Rosée → Brume | 1 km | 200 s |

Un combat gèle la marche restante. Sa durée s’ajoute au trajet ; quitter le champ de bataille relance les portions restantes. Les échéances et la distance restante sont sauvegardées, et un trajet déjà engagé ne peut pas être remplacé par une autre commande de déplacement. L’arrivée à Brume termine le tutoriel via la boucle autonome du serveur.

Une rencontre tire le groupe entier avant le début du combat : si trois gobelins sont tirés, ils sont tous présents simultanément, ciblables séparément et autonomes. L’interface indique le numéro de rencontre et le nombre d’ennemis visibles par rapport au groupe initial. Un long trajet peut ensuite déclencher d’autres rencontres, chacune avec son propre groupe.


## Combat tactique et progression du POC 0.9

Quinze presets sont disponibles : trois terrains pour chacun des cinq contextes (clairière, lisière, route, entraînement à Rosée et bois de Brume). Une case représente deux mètres. Le joueur marche à 6 km/h et le gobelin se déplace à 3 km/h en combat (respectivement 1,2 et 2,4 secondes de jeu par case). Les couvertures bloquent la marche et la ligne de vue. Le corps à corps porte à 1,5 case ; les classes à distance et les compétences de soutien portent à six cases. L’interface affiche uniquement les ennemis à six cases maximum et en ligne de vue, avec leurs PV, leur position et leur intention. Les autres ennemis ne sont pas transmis au client. Un clic sur une entité la sélectionne exclusivement ; un second clic la désélectionne. Un double clic fait marcher jusqu’à une case voisine. Le bouton pour se cacher apparaît uniquement si cette action est possible ; les indications de dépeçage disparaissent en s’éloignant des corps.

Explorer donne l’initiative : les joueurs apparaissent dissimulés et les mobs patrouillent. Un joueur visible et atteignable est poursuivi ; chaque membre du groupe garde son propre placement et sa dissimulation. Perdre un joueur de vue déclenche une recherche à sa dernière position connue, pendant 30 secondes de jeu (10 secondes réelles), puis la patrouille reprend. Un stun bloque déplacement, attaque et appel ; sans cible visible à son réveil, le mob reprend sa patrouille.

Un mob qui repère un ennemi, subit une première attaque ou voit l’ennemi s’éloigner peut appeler ses alliés. L’appel dure six secondes de jeu (deux réelles), comme son délai de réutilisation. Les dégâts ou un stun l’interrompent. Seuls les alliés vivants non avertis à moins de dix cases sont concernés. Ils reçoivent une dernière position connue, sans révélation magique d’un joueur caché.

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


## Incantations, invocations et continuité du serveur

Les compétences physiques ont une préparation de 0,4 seconde réelle, les invocations de 2 secondes et les autres sorts de 1,5 seconde. Le compte à rebours apparaît dans les actions du joueur. Le personnage reste immobile pendant cette durée. Les sorts non physiques demandent de la concentration : des dégâts effectifs, la mort ou un étourdissement interrompent l’incantation. L’énergie est consommée au départ ; la cible, sa portée et la ligne de vue sont vérifiées de nouveau à la résolution. Le délai général de 1,2 seconde commence au départ de l’action ; les délais propres des compétences commencent à leur résolution. Les déplacements entre zones se confirment dans un panneau de la page.

Les squelettes invoqués occupent des cases libres et se déplacent automatiquement. Ils attaquent l’ennemi visible le plus proche ; à distance égale, ils privilégient celui qui a le moins de PV. Les mobs peuvent les repérer et les attaquer. Les invocations suivent le rythme du serveur, même si leur maître ne lance aucune action.

Les patrouilles suivent des circuits étendus adaptés aux obstacles de chaque terrain. Les mobs détectent un joueur visible à six cases, comme la portée maximale des attaques à distance. Un appel ne commence que si un allié vivant non averti est à moins de dix cases ; les mobs qui voient déjà un adversaire sont avertis avant de décider d’appeler. Les spawns des groupes et des invocations sont vérifiés et les anciennes positions sur un obstacle sont corrigées lors de la simulation.

Une erreur de simulation ne ferme plus silencieusement le serveur. Sa trace est affichée dans le terminal ; une session défaillante est isolée des autres. Ce mécanisme conserve le service disponible et signale l’erreur, sans effacer les sauvegardes. Pour vérifier la version chargée après une mise à jour : `python -m pip install --force-reinstall .`, puis `python main.py`.

Le nécromancien dispose d’un bouton d’invocation personnelle dans les actions de combat, sans devoir se sélectionner sur la carte. Il conserve sa cible ennemie. Les boutons de combat restent en place pendant les actualisations pour préserver le clic et le focus clavier ; l’invocation devient temporairement désactivée pendant une incantation, un délai, un manque d’énergie ou lorsque la limite est atteinte.


## Vision partagée et contrôle des invocations (0.10)

Le groupe voit les ennemis observés à six cases maximum en ligne de vue par un joueur vivant ou une invocation vivante d’un maître vivant. Un ennemi invisible pour tous n’est envoyé à aucun client. Cette vision partagée ne modifie pas la portée ni la ligne de vue requises pour l’attaque du personnage.

Un clic sur une case inspecte les entités visibles de cette case dans le panneau de droite. Un clic sur une entité la sélectionne ; un clic sur une invocation personnelle prend son contrôle lorsque le personnage et son énergie le permettent. Les statistiques du personnage et de ses invocations sont accessibles dans les actions de combat et les caractéristiques. La sélection rapide permet de contrôler une invocation, toutes les invocations personnelles, de maintenir leur position ou de les rendre autonomes. Un double clic sur une case déplace les unités contrôlées ; sans unité contrôlée, il déplace le personnage. Sélectionner un ennemi propose un ordre d’attaque aux unités contrôlées, même si le maître est trop loin pour frapper lui-même.

Le coût du squelette est de 0,4 Mana par seconde réelle et par unité contrôlée. Il est configurable par type dans `CONTROL_RULES`, avec un coût nul possible. L’énergie du moteur étant entière, le Mana est payé par unités entières en avance ; le crédit restant est conservé entre deux prises de contrôle. Le temps écoulé est facturé également lors d’un changement de sélection : basculer rapidement de mode ne contourne pas le coût. L’épuisement, la mort ou un stun du maître rendent les unités autonomes. Les ordres sont vérifiés par le serveur : propriétaire, état, ressources, sélection sans doublon, chemins adjacents, couvertures et visibilité de la cible. Les PNJ alliés de combat ne sont pas encore présents dans le contenu du POC ; le menu apparaît pour les unités non joueuses personnelles disponibles, actuellement les squelettes.

### Interface de combat 0.10.1

La carte reste au centre, les statistiques des joueurs et invocations et leur contrôle à gauche, les ennemis et intentions à droite. La barre d’actions en bas conserve les emplacements de l’attaque simple et des sorts acquis ; les actions impossibles sont désactivées. Les panneaux latéraux défilent dans leur propre espace et ne repoussent plus la carte lors des mises à jour.

### Synchronisation et ressources de combat 0.10.2

Les réponses d’actualisation périmées ne remplacent plus l’état d’une commande plus récente. Les déplacements utilisent la dernière position reçue et une actualisation est demandée après chaque commande. En combat, les alliés et invocations n’affichent que leurs PV et ressources ; les caractéristiques détaillées restent dans la consultation hors combat.

La barre d’actions affiche les actions de l’entité contrôlée : personnage, invocation unique ou groupe. Une invocation unique peut lancer ses compétences offensives acquises avec son propre coût, sa portée, son incantation et son délai, validés par le serveur. Les personnages des autres joueurs ne peuvent pas être contrôlés.

### Actualisation et statuts 0.10.3

La cible sélectionnée reste conservée lors d’un clic de déplacement. Les actualisations continuent pendant les commandes ; les réponses périmées sont ignorées. Les cases, entités et cartes d’ennemis conservent leurs éléments interactifs entre les actualisations, ce qui permet de recevoir les positions sans suspendre les mises à jour pendant un double clic. Les statuts actifs sont visibles dans les informations du personnage et des ennemis.

### Déplacements et accès à Rosée 0.10.4

Les ordres de marche ne déclenchent ni ne prolongent le délai d’attaque de 1,2 seconde. La marche reste autorisée pendant ce délai, mais les incantations et étourdissements immobilisent toujours les personnages. Le ciblage des ennemis visibles reste disponible pendant la marche et le délai d’action. Le bouton « Rejoindre Village de Rosée » lance directement le trajet annoncé ; les boutons de route redondants sont supprimés. Le déplacement vers un point d’une autre zone depuis la consultation de carte conserve sa confirmation.

### Fiabilité des déplacements 0.10.5

Les entités et cases de combat restent attachées au DOM pendant les actualisations, afin de préserver les doubles clics. Pendant une requête, le dernier ordre de déplacement est conservé puis exécuté si le combat est toujours le même. Un ordre de marche peut utiliser une révision antérieure lorsque son numéro de combat correspond au combat actuel ; le serveur valide toujours le propriétaire, les contraintes d’action et le chemin depuis la position courante. Les cases du chemin déjà atteintes sont retirées sans déplacement instantané ni accélération. Les anciens clients sans numéro de combat conservent la vérification stricte de révision.

### Navigation directe 0.10.6

Sur les cartes générale et détaillée, un clic consulte le lieu ou le point et un double clic lance directement le déplacement. La confirmation en haut de l’écran est supprimée. Les éléments interactifs restent attachés entre les actualisations pour préserver le double clic. Les restrictions de voyage pendant un combat ou un trajet restent appliquées par le serveur.

Pendant un trajet dangereux, chaque point de contrôle ne tente désormais une rencontre que dans 25 % des cas, avant le calcul existant lié au niveau et au rang. Les combats de trajet sont ainsi environ quatre fois moins fréquents, sans modifier la recherche volontaire de monstres ni la taille des groupes.

### Affichage des ressources 0.10.7

Les fiches de personnage, d’invocations et d’ennemis affichent le nom, une barre avec la valeur courante/maximale pour les PV et chaque énergie, puis les statuts à droite avec leur durée restante en secondes réelles à une décimale. La durée affichée correspond au prochain tick d’effet et aux cycles restants ; les effets sur les invocations expirent désormais sur le même rythme.

### Retours de combat et dissimulation 0.10.8

La fabrication de la veste est marquée comme accomplie dans le journal de quête et la forge ; en groupe, l’interface précise si un compagnon doit encore fabriquer sa veste. Le combat affiche les derniers événements et un journal : lancement et fin de sorts, attaques, dégâts reçus, repérage et perte de ligne de vue. Une perte de PV apparaît aussi sur la fiche concernée.

Un personnage repéré perd sa dissimulation et ne peut pas se cacher simplement à sa dernière position connue. Il doit rompre la ligne de vue et quitter cette position. Un déplacement entre des cases couvertes conserve la dissimulation à vitesse réduite de moitié ; entrer à découvert ou être vu la supprime.

Les déplacements tactiques autorisent les diagonales pour les joueurs, invocations et mobs. Chaque pas diagonal prend √2 fois la durée d’un pas droit, également en marche dissimulée. Les chemins privilégient la distance parcourue et ne permettent pas de traverser le coin d’une couverture.

Tous les personnages vivants, invocations et mobs récupèrent par défaut 1 % de leurs PV maximum par minute de jeu (20 secondes réelles au ratio 1:3), même en combat. Les fractions de PV sont conservées jusqu’à atteindre un point entier ; la régénération ne dépasse pas le maximum et ne ressuscite pas les morts.

Pendant un trajet hors combat, une nouvelle destination recalcule l’itinéraire depuis la progression réelle sur le chemin : le groupe peut revenir en arrière ou poursuivre vers une autre route sans téléportation. Le journal du combat est placé sous les actions et reste replié par défaut.

Les pièces de forge ont des profils distincts : casque intelligence/sagesse, veste protection, gants force, jambières force/protection, bottes sagesse/protection et ceinture intelligence/sagesse. Les améliorations renforcent les bonus propres à chaque pièce. Les équipements existants reçoivent une fois les nouveaux bonus. Une marche dissimulée entre cases couvertes utilise la détection rapprochée (1,5 case), tandis que commencer une dissimulation reste impossible sous le regard d’un ennemi à distance.

Les invitations de salon sont valables 30 minutes réelles. Le bouton affiche un lien et un code partageables, avec la durée restante ; le tutoriel en groupe attend deux joueurs avant de démarrer. Le destinataire peut ouvrir le lien puis créer son personnage, ou coller le lien/code dans le formulaire. Sur un réseau local, partagez une adresse du serveur accessible au compagnon. La génération des identifiants de commande fonctionne aussi en HTTP local sans `crypto.randomUUID`.

Le client accepte 30 secondes de délai par requête sur les connexions mobiles et tunnels, utilise des requêtes JSON non mises en cache et reprend les actualisations au retour au premier plan ou du réseau. Les échecs d’actualisation déclenchent une reconnexion avec délai progressif, sans effacer le personnage. Les réponses de commandes mettent directement l’interface à jour. Pour un tunnel HTTPS, déclarer son adresse avec `python main.py --public-origin https://votre-tunnel.devtunnels.ms` ; les contrôles Host et Origin restent actifs.

Les commandes de déplacement et d’exploration incluent un contexte de monde validé par le serveur. Une évolution purement temporelle peut augmenter la révision sans bloquer ces commandes sur un tunnel lent ; un changement de lieu, de trajet ou de combat invalide toujours le contexte précédent.

Le serveur écrit les connexions, échecs HTTP/transport et actions demandées hors combat dans `.logs/network.log`, un fichier texte à lignes simples sans rotation. Les clés personnelles, invitations et corps de requêtes ne sont pas journalisés. `--log-directory` permet de changer le dossier. Le TLS d’un tunnel est terminé par le proxy et ses erreurs ne sont pas visibles depuis le serveur local. Le rafraîchissement distant est limité à une requête par seconde par client pour réduire le trafic et les refus du limiteur ; il reste automatique, sans bouton Actualiser.

Le chat global liste les joueurs actifs depuis moins d’une minute, avec un canal distinct par groupe. Les messages sont limités à 400 caractères et un envoi par seconde ; seuls les membres du groupe accèdent à son canal. Les textes sont rendus sans HTML. Le groupe conserve au maximum 200 messages en base ; le général fonctionne uniquement en direct, avec une file temporaire de 50 messages par connexion. Le tableau Succès et titres suit cette aventure sauvegardée : zones visitées, niveau maximum, créatures vaincues, meilleur temps de victoire et exploits (sans alerte, sans dégâts, rapide, duel contre un niveau supérieur, supériorité/infériorité numérique selon les joueurs vivants au début). Les entraînements ne donnent pas de succès ; la victoire complète est nécessaire. Les anciens combats ne permettent pas de reconstruire les exploits manquants.

Le chevalier inflige désormais `3 + 0,30 × Force` avec son attaque simple et `0,80 × dégâts de base + 0,45 × Force` avec Sword Slash, arrondis à l’entier inférieur avant les résistances. Le Slash reste à 10 Aura et conserve ses délais. Les autres classes gardent leurs coefficients.

Chaque Sword Slash réussi sur un ennemi vivant ajoute un saignement indépendant : trois pulsations espacées de deux secondes réelles, à `max(2, Force × 0,05)` dégâts bruts par pulsation. Les cumuls ont leurs propres durées et restent sauvegardés ; les résistances s’appliquent. Le saignement peut vaincre le mob et accorde alors les récompenses normales une seule fois.

Le champ de bataille possède une case Sortie au bord gauche. Un joueur vivant qui l’atteint fait quitter le combat au groupe, même si des ennemis restent vivants. Le trajet suspendu reprend ; les corps non dépecés sont abandonnés. Fuir le premier combat permet de recommencer l’exploration, sans valider sa victoire. Aucun bouton de sortie n’est affiché et une commande de sortie hors de cette case est refusée.

Le navigateur demande des blocs JSON avec `X-RPG-Bundles: 1` et renvoie leurs empreintes dans `X-RPG-Bundle-Hashes`. Le serveur prépare les blocs et ne retransmet que les valeurs modifiées ; la carte, les statistiques et les intentions conservent leur interface tant que leurs données ne changent pas. Les autres clients conservent les réponses complètes de l’API. Les actions restent validées par le serveur. Le premier chargement reçoit toujours tous les blocs et une reconnexion avec un nouveau personnage réinitialise les empreintes.

Pour reproduire le test de charge sur une base temporaire : `python scripts/verify_load.py --seconds 45`. Il lance 30 clients HTTP locaux (15 combats indépendants avec IA active et 15 joueurs en ville), avec une actualisation par seconde et des déplacements en combat toutes les quatre secondes. Les PV des joueurs de test sont augmentés pour maintenir les combats. Le rapport est enregistré dans `test/load/30_users.json`. Ce test ne mesure pas la latence d’un tunnel ou d’un hébergement distant. Le serveur limite les requêtes d’état à 300 par minute et par personnage et les commandes à 60 par minute ; la limite IP globale tient compte de plusieurs joueurs derrière un proxy.

Mesures locales : 30 joueurs mixtes pendant 45 s, 1 350 états et 180 déplacements, aucune erreur, p95 111 ms ; 30 joueurs tous en combat pendant 30 s, 900 états et 240 déplacements, aucune erreur, p95 156 ms. Les réponses différentielles réduisent respectivement le volume moyen de 64,6 % et 58 % par rapport au premier chargement. Reproduction du second scénario : `python scripts/verify_load.py --seconds 30 --combat-users 30 --output test/load/30_combat_users.json`. Les actions du navigateur reçoivent désormais une confirmation courte ; la lecture d’état transmet ensuite les blocs modifiés. Les autres clients peuvent conserver une réponse complète.


Version 0.10.20 : le client calcule les itinéraires de combat et les trajets entre lieux, y compris les chemins possibles depuis les extrémités d’un trajet en cours. Le serveur vérifie les cases, les liaisons connues, la destination, les droits, l’état du personnage et les délais ; il conserve le contrôle de la vitesse, des rencontres et de l’IA. Les clients qui ne proposent pas d’itinéraire gardent le calcul serveur pour compatibilité.

Les connexions HTTP sont persistantes, avec délai d’inactivité de 5 secondes et plafond de 128 connexions. Les chemins fixes sont mis en cache avec une limite de 4 096 entrées ; les copies renvoyées sont indépendantes. Le serveur ne recalcule plus les patrouilles existantes ni les déplacements des mobs avant leur échéance. Les vues sont préparées par personnage pendant la simulation, mises en cache sur 256 entrées et réutilisées seulement pour la même révision avec moins de 200 ms d’ancienneté. La simulation libère le verrou entre les sessions. Les lectures d’état n’écrivent plus systématiquement l’horloge ou la présence ; la présence est renouvelée au plus toutes les 10 secondes. SQLite utilise WAL avec synchronisation FULL. Les commandes arrivant dans une fenêtre de 2 ms sont regroupées par lots de 32 au maximum, chaque commande garde son isolation et les réponses ne sont confirmées qu’après la sauvegarde du lot.

Le test de charge lance le serveur dans un processus séparé des clients et conserve une connexion HTTP par joueur, comme le navigateur. L’option `--max-p95 40` échoue si le 95ᵉ percentile des états ou des déplacements atteint 40 ms. Les joueurs des fixtures ont des PV augmentés pour maintenir les combats ; l’IA fonctionne normalement. Ces mesures concernent le local et ne garantissent pas toutes les requêtes sous 40 ms ni la latence d’un tunnel.

| Scénario | États | Déplacements | p95 états | p95 déplacements | Erreurs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30 combats, 45 s, 4 états/s/joueur | 5 400 | 360 | 31,56 ms | 37,01 ms | 0 |
| 15 combats + 15 en ville, 30 s, 4 états/s/joueur | 3 600 | 120 | 25,78 ms | 29,63 ms | 0 |

Le maximum observé pour les états est respectivement 68,22 ms et 59,97 ms. Rapports : `test/load/30_combat_optimized.json` et `test/load/30_mixed_optimized.json`. Reproduction : `python scripts/verify_load.py --seconds 45 --combat-users 30 --poll-interval .25 --max-p95 40 --output test/load/30_combat_optimized.json`, puis `python scripts/verify_load.py --seconds 30 --combat-users 15 --poll-interval .25 --max-p95 40 --output test/load/30_mixed_optimized.json`.


Version 0.10.21 : les messages du général sont distribués uniquement aux connexions actives dans le même périmètre. Une nouvelle connexion de navigateur commence avec une file vide, même pour un personnage déjà connecté dans un autre onglet. Les messages du général ne sont pas stockés en base et ne reviennent pas après un redémarrage. Leur texte complet est conservé en lignes JSON dans `.logs/chat.log`, sans jeton d’accès. Les anciens messages généraux présents en base sont transférés dans ce log au démarrage, puis retirés de la table. Les files expirent après 60 secondes sans requête et sont limitées à 50 messages, huit connexions par personnage et 2 048 connexions au total. Le navigateur reçoit les messages à l’actualisation automatique suivante. Le chat du groupe garde son fonctionnement précédent.

La version 0.10.22 affiche la meilleure différence de niveau remportée en duel solo dans le titre « Briseur de limites (+N niveaux) ». L’écart est enregistré au début du combat ; les victoires avec un écart inférieur ne le réduisent pas.

La version 0.10.24 organise Rosée et Brume autour d’une entrée, d’une place centrale et de rues. Les bâtiments d’une même rue se suivent : les itinéraires client et leur validation serveur utilisent ces liaisons, également affichées sur la carte détaillée. Les maisons, auberges et la boutique sont des repères sans interaction pour le moment.

La version 0.10.25 lance les nouveaux tutoriels web directement dans une forêt fixe à explorer à pied. La case du chemin rapide ouvre la carte générale. Rosée (64 × 40 cases) et Brume sont des cartes tactiques zoomables, y compris hors combat. Rosée rejoint la lisière, la forêt et la grotte ; la lisière rejoint aussi le campement gobelin. La grotte comprend trois salles, dont la dernière est une impasse. La forêt possède une sortie complète vers les chemins rapides.

Les terrains, obstacles et positions initiales des ennemis de ces zones sont prédéfinis. Les combats aléatoires restent réservés aux trajets rapides. Les zones explorées, corps et ennemis survivants restent en mémoire de la partie et sont enregistrés avec elle : le retour conserve son état tant que le délai de repop de trois minutes de jeu sans joueur n’est pas atteint. La carte se découvre en marchant ; les ennemis vivants restent soumis à la visibilité et aux couvertures. La molette et les boutons permettent de zoomer, les flèches déplacent la vue et « Suivre le personnage » recentre la caméra.

Une sortie vers une autre carte transporte le groupe et ses invocations. Seuls les ennemis alertés qui voient le personnage franchir cette sortie et peuvent agir le poursuivent. Une sortie complète vers la vue générale arrête la poursuite. Les interactions avec Mira et la forge demandent de se trouver près de leurs positions sur la carte, sans ennemi qui menace le personnage. Pour une partie déjà commencée, « Explorer à pied » ouvre la carte fixe du lieu depuis la vue générale. L’API `tutorial` accepte `field_mode: true` ; sans ce paramètre, les intégrations existantes conservent leur parcours précédent.

Test de charge des cartes fixes : `python scripts/verify_load.py --fixed-zones --seconds 30 --combat-users 15 --poll-interval .25 --output test/load/30_fixed_zones.json`.

Les gobelins vaincus dans les zones de Rosée avant d’accepter la quête de Mira sont pris en compte, afin qu’une zone déjà débarrassée de ses ennemis ne bloque pas le tutoriel. Les poursuivants atteignent la carte suivante après le temps nécessaire pour rejoindre la sortie.

Mesure 0.10.25 : 30 joueurs, dont 15 en combat sur les cartes fixes et 15 à Rosée, pendant 30 s à 4 actualisations/s. 3 600 états et 120 déplacements, aucune erreur ; p95 des états 35,33 ms, p95 des déplacements 39,58 ms. Le maximum des états reste à 99,25 ms : ces résultats sous 40 ms concernent le p95 en local. Rapport : `test/load/30_fixed_zones.json`.

La version 0.10.26 fait réapparaître les ennemis tués lorsque leur zone est restée sans joueur pendant au moins trois minutes de jeu (60 secondes réelles au ratio 1:3). Un retour avant ce délai ne provoque aucune réapparition et la prochaine sortie redémarre le délai. Aucun repop pendant la présence du groupe. Les survivants et anciens corps sont conservés ; une créature qui poursuit le groupe dans une autre zone n’est pas dupliquée. La réapparition est calculée à la prochaine entrée dans la zone, sans simulation supplémentaire des zones vides.

Le zoom 0.10.26 fonctionne également dans les anciens combats, sur la carte générale et sur les cartes détaillées. Cliquez sur une carte pour la choisir, puis utilisez +/− ou la molette ; les flèches déplacent la vue. Le zoom est conservé lors des actualisations. Les cartes occupent davantage de hauteur et les commandes sont utilisables sur mobile.

La vision des personnages joueurs passe à 12 cases, contre 6 pour les invocations et la détection normale des monstres. La vision partagée respecte toujours les obstacles et ne permet pas d’attaquer au-delà de la portée propre à l’action. La découverte du terrain utilise également ce rayon de 12 cases pour les joueurs vivants.

## Alpha 0.11.0a1 — cartes et passages

Les déplacements rapides ouvrent la carte locale uniquement à la destination finale : les villages intermédiaires ne détournent plus le trajet vers le campement. Les arrivées utilisent le passage correspondant à la provenance ; quitter puis rejoindre une zone conserve son passage de retour.

Les cartes fixes et les terrains de rencontre disposent de décors de forêt, de village ou de grotte, de chemins, de cours d’eau et de ponts. L’eau bloque les déplacements, y compris ceux des ennemis, mais reste transparente à la ligne de vue. Les ponts sont praticables. Les positions des anciennes sauvegardes sont replacées sur une case praticable lorsque le nouveau terrain les recouvre.

## Éditeur graphique externe — alpha 0.11.0a2

Depuis le dépôt, lancer `python map_editor.py` après installation. Le paquet fournit aussi `jeux-rpg-map-editor` et `python -m jeuxRPG.multiplayer.map_editor`. L’éditeur de bureau utilise Tkinter, fourni avec l’installation Python officielle Windows ; sur Linux, installer le paquet Tkinter de la distribution. Il ne se connecte pas au serveur du jeu.

Sélectionner une carte, puis peindre par clic ou glisser : sol, arbres, rochers, maisons, eau, ponts, chemins, fleurs, herbe, cristaux et campements. Ajouter des apparitions de gobelins, des PNJ et des passages de téléportation. Pour un passage, choisir l’identifiant exact de la carte destination et la case d’arrivée `x,y` ; une destination vide rejoint les chemins rapides. Un PNJ dispose d’un nom et d’un dialogue. Son propriétaire peut être `leader` pour le premier joueur du groupe, un identifiant joueur précis, ou vide pour un PNJ fixe. Les outils Inspecter et Effacer, l’annulation Ctrl+Z, le zoom, les barres de déplacement et les propriétés de carte permettent de corriger la scène. Les apparitions utilisent actuellement l’espèce gobelin ; les PNJ ajoutés proposent un dialogue, sans générateur de quêtes ou de compétences.

Enregistrer sous `maps.json`. La sauvegarde valide les limites des cases, les obstacles, les destinations, les points d’arrivée et l’accessibilité des passages, PNJ et apparitions. Elle conserve les cartes nécessaires au tutoriel. Le remplacement du fichier est atomique. Pour utiliser ce fichier dans PowerShell :

```powershell
$env:RPG_MAPS_FILE = (Resolve-Path .\maps.json).Path
python main.py
```

Redémarrer le serveur après une modification. Tester les cartes dans une nouvelle session : les ennemis et le terrain exploré des sessions existantes restent sauvegardés. Les nouvelles cartes deviennent accessibles en reliant un passage d’une carte existante à leur identifiant. Les changements du fichier sont réservés à l’opérateur local ; aucune API publique d’édition n’est ouverte.

Par défaut, les invocations suivent leur propriétaire à distance de deux cases quand elles n’ont aucune cible. Elles conservent leurs attaques automatiques ; le contrôle manuel et les incantations prennent la priorité. Les PNJ liés suivent aussi leur joueur et accompagnent le groupe lors des changements de zone. Les PNJ fixes, comme Mira et Léon, restent fixes ou conservent leur itinéraire propre. Les PNJ d’escorte ajoutés par l’éditeur sont pacifiques et ne disposent pas encore d’une IA de combat.

Le [guide complet du builder](docs/BUILDER_GUIDE.md) décrit les outils, les noms de cartes, les options de téléportation, les retours automatiques et le chargement des fichiers. Depuis l’alpha 0.11.0a3, la liste affiche les noms avec leurs identifiants stables et les noms modifiés sont repris dans les vues du monde.

## Alpha 0.11.0a4 — catalogue JSON et forêt de départ

Les définitions des cartes fixes et des quinze presets de rencontre sont maintenant dans le dossier [jeuxRPG/maps](jeuxRPG/maps/README.md), sous forme de JSON. Elles sont incluses dans le paquet installé. Le builder lancé depuis le dépôt ouvre `jeuxRPG/maps/world.json` par défaut ; le serveur peut aussi charger un dossier de plusieurs JSON via `RPG_MAPS_FILE`.

La forêt de départ comporte trois secteurs raccordés : sentier oublié, vieux pont et route entretenue. Ils reprennent le terrain des références, avec quatre colonnes de chevauchement identiques. La troisième carte dispose d’un chemin en bon état et de la sortie vers les chemins rapides ; les retours restent possibles. [Vue d’ensemble](docs/STARTING_MAPS.svg).

## Alpha 0.11.0a5 — builder avancé

Le builder propose des remparts de fortune X et des murs M, bloquant déplacement et vue. Les spawners choisissent leur espèce (gobelin, orc, dragonnet), leur niveau et un groupe de 1 à 5 créatures. Les patrouilles se dessinent sur la grille et sont conservées au repop. Le catalogue des espèces est dans `maps/mobs.json`.

Les propriétés et la création de carte proposent le rattachement de zone, le niveau de zone et une surcharge locale. Le niveau d’un spawner vide hérite de la carte, puis de sa zone. Recherche par nom/identifiant, filtres par zone et niveau, pinceaux 1/3/5, visibilité des calques, duplication, suppression contrôlée, validation et synchronisation des raccords facilitent la construction. Le [guide complet](docs/BUILDER_GUIDE.md) détaille ces outils.

## Alpha 0.11.0a6 — écran tactique et raccords

L’interface tactique occupe toute la fenêtre, avec une grande carte centrale, les alliés à gauche, les ennemis à droite et les actions en bas. Au premier clic, le navigateur passe en plein écran s’il autorise cette fonction ; Échap permet d’en sortir. L’interface conserve son occupation de la fenêtre si le plein écran natif est refusé ou indisponible. Les panneaux latéraux défilent indépendamment.

Les sorties découvertes sont signalées par un repère ⇥, ramené au bord de la vue si la sortie est hors cadrage. Double-cliquer ce repère lance la marche vers le passage.

Le builder propose **Créer un secteur relié** : direction, chevauchement, décor partagé, rattachement de zone et passages aller-retour automatiques. Les chemins d’accès sont dégagés. Le guide décrit cette création et l’usage des téléportations pour les salles indépendantes.

## Alpha 0.11.0a7 — assemblage graphique des cartes

Le builder propose **Assemblage des cartes** : aperçu des blocs, déplacement sur grille, zoom, collage ou espacement précis, chevauchement, création de passages et fusion de cartes d’une même zone. La fusion recalcule les entités, patrouilles et arrivées externes, retire les passages internes et protège les cartes obligatoires. Les changements sont annulables et enregistrés dans les JSON. Le [guide du builder](docs/BUILDER_GUIDE.md) décrit les règles de fusion et de placement.

## Alpha 0.11.0a8 — passages, rues et voyages éditables

Le builder ajoute **Trajets / rues**, la configuration des distances et durées des chemins rapides, **TP par clics** pour choisir les cases du passage et du retour, et **Déplacer** pour les PNJ, passages, spawners, décors et points de patrouille. Les salles `cave_2` et `cave_3` peuvent être fusionnées dans `cave_1`. Les bundles transmettent désormais l’identifiant de carte fixe et ses interactions ; les repères des TP restent visibles hors cadrage et sans découverte préalable, avec séparation des repères superposés.

## Alpha 0.11.0a9 — aperçu du rendu et rotation des ponts

Le builder ouvre un **Aperçu rendu final** autonome dans le navigateur, avec le rendu de terrain partagé avec le jeu, zoom, déplacement de la vue et repères facultatifs. Les modifications non enregistrées sont incluses. **Pont °** règle l’orientation au placement ; **Rotation pont** tourne un pont existant par pas de 90°. L’orientation est enregistrée dans les JSON et préservée dans les raccords et fusions.

## Contrôleur du projet

`python controller.py` ou `jeux-rpg-controller` ouvre le contrôleur graphique : builder, quêtes, espèces, succès et titres, PNJ et paramètres du monde. Voir [le guide complet](docs/CONTROLLER_GUIDE.md). Enregistrer puis redémarrer le serveur pour appliquer les définitions.

## Alpha 0.11.0a20 — accès du builder et parcours client

Les textures des ponts restent attachées au SVG pendant les actualisations. Les secteurs associés à un village sont reliés aux chemins rapides ; sortir de la forêt permet de rejoindre Rosée. Les actions tactiques identifient le combat en cours et sont vérifiées sur l'état actuel, sans être bloquées par une simple révision de simulation.

Le builder refuse les cartes dont une arrivée de TP, l'apparition initiale, un PNJ, un atelier, un spawner ou une sortie est inaccessible. Le contrôleur affiche ces problèmes dans son diagnostic. Voir le [guide du builder](docs/BUILDER_GUIDE.md).

Le [parcours client sur les données actuelles](docs/DEMO_UI.md) utilise des clics de l'interface et une base temporaire, sans injection d'état de jeu. Il complète les tests sur le monde de référence. Le workflow **Parcours UI du monde actuel** permet aussi de le lancer manuellement dans GitHub Actions.
