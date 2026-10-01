# Arène, sauvegarde et artisanat

## Jouer

```bash
python -m pip install '.[test]'
python main.py
```

Le lancement enchaîne les combats sans limite dans la zone actuelle ; dans les agglomérations, il fabrique et équipe automatiquement les armures disponibles. `Ctrl+C` demande un arrêt après le combat en cours. Chaque combat est limité à 200 rounds : sans vainqueur, il devient un match nul plutôt qu'une boucle bloquée.

La progression reprend automatiquement depuis `.data/adventure/player.json`. Le personnage, l'XP, les statistiques, les énergies, les matériaux, les objets, les pièces équipées, les compteurs et l'état aléatoire sont enregistrés ensemble. Une écriture temporaire puis un remplacement atomique évitent de tronquer la dernière sauvegarde valide. Une sauvegarde invalide provoque une erreur de chargement ; elle n'est pas remplacée par un nouveau personnage.

```bash
python main.py --class Necromancien --name Alice --save .data/alice.json
python main.py --battles 20 --interval 0 --save .data/alice.json
python main.py --interactive --save .data/alice.json
```

`--battles` limite les nouveaux combats de cette exécution. Sans cette option, la boucle continue jusqu'à l'arrêt demandé. `--interval` règle la pause entre combats de 0 à 60 secondes. `--no-auto-craft` permet de conserver les matériaux. `--json` affiche le rapport détaillé de chaque combat. Les options de création classe/nom/seed sont utilisées uniquement si le fichier choisi n'existe pas.

## Mode interactif

| Commande | Action |
|---|---|
| `combat` | Disputer un combat et sauvegarder le butin |
| `personnage` | Voir niveau, XP, victoires et bonus d'équipement |
| `inventaire` | Voir matériaux, objets et pièces équipées |
| `recettes` | Voir les recettes découvertes, leurs identifiants, ingrédients et stocks |
| `craft Goblin:1:helmet` | Fabriquer un casque de gobelin de rang 1 si les matériaux sont disponibles |
| `equiper item-000001` | Équiper un objet possédé ; l'ancienne pièce reste dans l'inventaire |
| `retirer helmet` | Retirer casque ; autres emplacements : `chest`, `boots` |
| `quitter` | Sauvegarder et quitter |

Le mode interactif laisse le craft au joueur. Les opérations de craft, d'équipement et de retrait déclenchent une sauvegarde.

## Créatures et génération

| Créature | Matériau d'armure | Trophée | Attribut de spécialité |
|---|---|---|---|
| Gobelin | Cuir | Dent | Force |
| Orc | Peau | Défense | Endurance |
| Dragonnet | Écaille | Griffe | Force |
| Gardien de pierre | Carapace | Noyau | Endurance |
| Créature arcanique | Étoffe | Cristal | Intelligence |
| Créature sacrée | Plume | Relique | Sagesse |

Une victoire donne 2 à 4 matériaux et 1 à 2 trophées de la créature. Défaites et matchs nuls ne donnent aucun butin. Le rang vaut `1 + (niveau de la créature - 1) // 5` ; une nouvelle famille/rang de matériaux révèle automatiquement trois recettes.

- Casque et bottes : 2 matériaux + 1 trophée chacun.
- Plastron : 3 matériaux + 1 trophée.
- Panoplie complète : 7 matériaux + 3 trophées, ou un assemblage de pièces déjà fabriquées.

Chaque pièce améliore les HP, l'endurance et l'attribut de sa famille. Trois pièces de la même famille **et du même rang** donnent en plus 20 HP et 3 endurance par rang. Les bonus sont recalculés au remplacement et à la reprise, sans cumul artificiel. Le craft automatique privilégie une panoplie complète plus puissante quand il peut la terminer ; sinon il remplit les emplacements vides ou améliore leur rang. Aucun objet n'est détruit lors d'un remplacement.

## Règles de l'arène

Les ennemis sont choisis dans la population de la zone. Leur niveau vise un niveau en dessous de celui du personnage, borné par les niveaux de la zone et le plafond du monde. Leur génération applique directement les mêmes gains de statistiques que la progression existante, sans rejouer des milliers de montées de niveau.

Après chaque combat, le personnage récupère ses HP/énergies, ses effets temporaires et cooldowns sont retirés. Une défaite conserve le niveau, l'XP et l'inventaire ; elle augmente le compteur de défaites et relance une rencontre. Le prêtre dispose d'une frappe de bâton spécifique à l'arène pour progresser en solo. Les victoires des invocations attribuent l'XP à leur maître.

La simulation courte précédente reste disponible avec `python main.py --mode simulation --floors 2`. Pour compatibilité, `--floors 2` seul sélectionne aussi la simulation.

L'arène est une application locale avec un seul processus par sauvegarde. Elle n'est pas un serveur multijoueur ; ne lancer pas deux instances qui écrivent le même fichier. Les sauvegardes du bot externe ne sont pas converties automatiquement vers ce nouveau format.

## Définitions de contenu

Les règles et recettes décrites ci-dessus sont celles du catalogue livré par défaut. Elles proviennent désormais de `jeuxRPG/resources/catalog.json`. Le moteur ne crée aucune définition de contenu au lancement. Les matériaux, recettes, emplacements et compositions de panoplie peuvent être ajoutés dans un fichier JSON d'extension. Le mode interactif et le craft automatique les découvrent sans modification de la CLI. Voir [RESOURCES.md](RESOURCES.md).

La carte, les sous-espèces, les boss, les auberges, les restrictions de craft et les plafonds des mondes sont décrits dans [WORLD.md](WORLD.md).

Les ateliers de village autorisent uniquement les objets dont le niveau requis est strictement inférieur à la moitié du niveau du village. Cette règle s’applique aussi au craft automatique et aux villages fondés. Voir FRONTIER.md pour les niveaux et les bornes.
