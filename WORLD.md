# Mondes, zones et voyages

Lancer `python main.py --interactive` pour explorer en ligne de commande. Les définitions sont présentes dans `jeuxRPG/resources/worlds.json` et sont chargées avec le catalogue. Aucun monde ni aucune définition de ressource n'est créé au lancement.

## Carte jouable

| Monde | Niveau maximal | Zone principale |
| --- | ---: | --- |
| Terres de l'Aube | 20 | Capitale de l'Aube |
| Empire des Cendres | 40 | Capitale des Cendres |
| Confins oubliés | 80 | Capitale des Confins |

Chaque monde comprend une capitale dans sa zone principale, un village dans les terres de bas niveau, une forêt, une ville dans les terres de niveau moyen, des montagnes et deux forteresses abandonnées aux extrémités des chemins. Les zones habitées et sauvages forment une toile avec des boucles et plusieurs itinéraires. Chaque monde possède son propre réseau. Les forteresses restent des destinations terminales aux frontières, accueillent des boss et n’offrent aucun service. Les capitales sont reliées par des chemins de portail, eux aussi soumis aux risques de voyage.

Les niveaux des zones déterminent la plage des ennemis et le niveau minimal d'entrée. Les rencontres utilisent uniquement la population déclarée dans la zone. La commande `carte` affiche les mondes, les zones, leurs services, leurs niveaux, leurs populations et les chemins. `chemins` affiche les sorties accessibles depuis la position actuelle. La carte est un graphe maillé de 27 zones, 30 chemins routiers et 9 repères hors route, sans coordonnées ni interface graphique ; elle pilote les rencontres et les services de l'aventure. Les anciennes API de navigation entre bâtiments restent disponibles aux autres utilisateurs du paquet.

## Commandes

| Commande | Rôle |
| --- | --- |
| `carte` | Afficher la carte complète et la position |
| `chemins` | Afficher les chemins au départ de cette zone |
| `voyager aube-capitale-village` | Suivre un chemin, dans un sens ou l'autre |
| `auberge nuit` | Passer le jour jusqu'à 18 h |
| `auberge jour` | Passer la nuit jusqu'à 6 h |
| `combat` | Affronter une créature de la zone actuelle |
| `personnage` | Voir le niveau réel, le niveau effectif, l'heure et les services |
| `craft Goblin:1:helmet` | Fabriquer dans un atelier, selon la limite du village |

Un voyage prend plusieurs heures. Les rencontres proviennent du croisement réel avec des PNJ ou des patrouilles suivant leurs itinéraires et horaires ; aucun tirage aléatoire ne déclenche un événement de voyage. Des patrouilles supplémentaires sont actives la nuit. Une défaite ou un match nul interrompt le voyage et laisse le personnage dans sa zone de départ. Une victoire permet de poursuivre. Les combats consomment une heure. L'heure, la position, les constructions, les découvertes et les itinéraires sont sauvegardés.

Les auberges des villages, villes et capitales permettent d'attendre le prochain début de jour ou de nuit sans embuscade et restaurent la santé et les énergies. Si l'heure choisie est déjà atteinte, le séjour dure 24 heures. Les villages proposent une auberge et un atelier limité aux objets de niveau strictement inférieur à la moitié du niveau du village. Les villes et capitales conservent leurs ateliers habituels. Cette limite concerne aussi le craft automatique. L'équipement et le retrait d'objets restent possibles partout.

## Sous-espèces et boss

Une créature peut déclarer `parent`, `variant` (`normal`, `subspecies` ou `boss`), `stat_multiplier` et `loot_multiplier`. Les parentés peuvent former plusieurs générations ; les références absentes et les cycles sont refusés. Les variantes ont leur propre définition explicite de classe et de butin : elles peuvent partager les matériaux de leur espèce parente ou déclarer leurs propres matériaux et recettes.

Le catalogue fournit notamment le gobelin forestier, l'orc des cendres, le roi gobelin, le seigneur orc et le dragon ancien. Les boss multiplient leurs statistiques et leur butin selon les valeurs déclarées.

## Plafond de monde

Le niveau réel et l'expérience sont conservés lorsque le personnage entre dans un monde inférieur. Son niveau effectif en combat devient `min(niveau réel, maximum du monde)`. Au plafond, le moteur utilise un combattant temporaire de la même classe, avec les statistiques, énergies et compétences acquises jusqu'à ce niveau, plus les bonus d'équipement autorisés. Les compétences des niveaux supérieurs ne sont pas conservées dans ce combattant. La progression permanente continue à recevoir l'expérience gagnée, sans augmenter le niveau effectif au-delà du plafond.

Le niveau requis d'un objet est `minimum_level + (rang - 1) * levels_per_tier`. Par défaut, le rang 5 requiert le niveau 21 : il est interdit dans le monde de l'Aube, plafonné à 20. À l'entrée d'un monde inférieur, les objets dépassant son maximum sont automatiquement retirés de l'équipement et restent dans l'inventaire. Le joueur peut les remettre après avoir rejoint un monde autorisé. Le craft manuel peut produire un objet trop puissant, mais l'équipement le refuse ; le craft automatique ignore ces objets.

Les sauvegardes antérieures sans position reprennent dans la capitale de départ, avec leur progression et leur inventaire. Une position sauvegardée devenue absente provoque une erreur explicite plutôt qu'une téléportation silencieuse.

## Ajouter du contenu

Les sections `worlds`, `zones` et `paths` sont extensibles via des fichiers JSON supplémentaires. Une zone référence un monde, des niveaux, une population et des services. Un chemin référence deux zones, une durée, deux risques et un éventuel sens unique. Le catalogue contrôle les références, les limites de niveaux, les chemins dupliqués et l'accessibilité depuis le départ.

Pour ajouter une sous-espèce à une zone existante sans remplacer celle-ci, ajouter sa définition dans un nouveau fichier avec une liste `zones`, par exemple `["aube-foret"]`. Sa population est ajoutée à celle de cette zone au chargement. Pour un nouveau monde, déclarer ses zones et au moins un chemin le reliant à la carte. La validation exige que le risque nocturne soit supérieur au risque diurne.

Un catalogue historique sans géographie reste lisible pour compatibilité avec les intégrations existantes ; utiliser les sections de carte pour bénéficier des restrictions de lieux et des plafonds de monde. Les ajouts se prennent en compte au redémarrage. Voir aussi `RESOURCES.md`.

Les sentes, les zones cachées, la création de villages, les relais et la simulation autonome sont détaillés dans [FRONTIER.md](FRONTIER.md). Les champs historiques `day_risk` et `night_risk` restent lisibles pour compatibilité ; le moteur de voyage ne les utilise plus pour tirer des événements.
