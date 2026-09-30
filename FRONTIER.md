# Exploration, fondation et activité du monde

Les ressources de `jeuxRPG/resources/frontier.json` déclarent les repères, zones cachées, sites stratégiques, ressources récoltables, constructions, PNJ et patrouilles. Les définitions sont chargées au lancement ; seuls les états de partie et les réalisations du joueur sont écrits en sauvegarde.

## Hors des routes

`observer` montre les repères visibles et les PNJ présents. Les descriptions indiquent une direction et un élément reconnaissable : grand rocher, arbre courbé ou filet d'eau. `explorer <repere>` suit ce repère en dehors des routes. Le retour suit le même repère lorsque la sente est bidirectionnelle. Le moteur vérifie la position et le niveau requis, et avance l'horloge du monde pendant le déplacement.

Chaque monde contient deux zones cachées : une clairière et une grotte, accessibles par des repères mais sans route initiale. La carte ne montre ces zones qu'après leur découverte. Il existe aussi une sente alternative entre capitale et village. Aucun repère ne permet de se téléporter depuis un autre lieu.

Exemple depuis la capitale de l'Aube :

```text
voyager aube-capitale-foret
observer
explorer aube-rocher
observer
explorer aube-source
```

## PNJ et main-d'œuvre

Les compagnies de bâtisseurs, caravanes marchandes et gardes parcourent des circuits routiers et s'arrêtent aux étapes. Leur position dépend de l'horloge et de leur programme. Un déplacement affiche les PNJ réellement croisés. `recruter aube-worker` engage les quatre bâtisseurs de la compagnie rencontrée ou visible. Ils deviennent la main-d'œuvre accompagnant le personnage et quittent leur circuit autonome. Une compagnie ne peut pas être recrutée deux fois.

Les rencontres de voyage ne sont pas tirées au hasard. Le moteur compare les positions au même instant : deux voyageurs qui occupent des parties communes d'une route à des instants différents ne se rencontrent pas. Les patrouilles hostiles utilisent également des itinéraires ; certaines sont actives la nuit. Les mécanismes existants de résolution des actions de combat et de quantité du butin conservent leur état aléatoire sauvegardé, indépendamment de cette simulation de déplacement.

## Camps et villages

`recolter` collecte les ressources déclarées sur le site et consomme une heure. Les rendements livrés sont fixes : quatre bois et trois pierres. Les matériaux de construction sont rangés dans l'inventaire comme les autres matériaux.

| Construction | Bois | Pierre | Travailleurs | Durée |
| --- | ---: | ---: | ---: | ---: |
| Camp | 4 | 2 | 2 | 4 h |
| Passage de camp à village | 16 | 12 | 4 | 12 h |
| Raccordement routier | 8 | 6 | 2 | 6 h |
| Relais | 6 | 4 | 2 | 4 h |

Ces coûts proviennent du catalogue. Les travailleurs fournissent l'effort pendant la durée du chantier et restent disponibles ensuite. Les matériaux sont consommés. Une main-d'œuvre ou un stock insuffisant empêche la construction sans consommation partielle.

`camp "Passage des Sources"` installe un camp sur un site autorisé. `dormir jour` ou `dormir nuit` permet d'y attendre et récupérer. `fonder` transforme le camp en village uniquement si le site est stratégique. `observer` indique le motif : carrefour, eau douce et passage naturel, ou col contrôlant les accès. Les grottes encaissées ne permettent pas cette transformation.

Le village prend le nom du camp et dispose d'une auberge. Comme les villages existants, il n'a pas d'atelier : le craft reste réservé aux villes et capitales. Un camp ou village occupe sa zone existante ; la population de créatures décrit les environs. Il ne modifie pas le catalogue statique.

## Raccordements et relais

Depuis un village fondé, `relier aube-capitale` construit une route vers une agglomération découverte du même monde. Les raccordements dupliqués et intermondes sont refusés. La route devient immédiatement empruntable dans les deux sens. Elle désenclave une zone cachée devenue habitée.

Les PNJ desservent les nouveaux villages raccordés à leur circuit. Leur nouveau programme commence au prochain retour au départ du circuit, afin de conserver leur position pendant l'ouverture du chantier. L'historique de ces changements est sauvegardé ; il fonctionne aussi lorsque l'horloge est avancée de plusieurs milliers d'heures d'un seul coup.

`relais <chemin>` ajoute un relais à un chemin accessible depuis la position actuelle, d'une durée d'au moins deux heures. `halte <chemin>` y fait une étape à mi-parcours. `auberge jour` ou `auberge nuit` permet de se reposer au relais. `voyager <meme-chemin>` termine le trajet restant. La position au relais et la progression du voyage sont sauvegardées. Les autres sorties, le craft, les camps et les récoltes ne sont pas accessibles depuis une halte routière.

## Un monde sans joueur

La simulation ne crée aucun personnage et peut fonctionner en continu :

```bash
python main.py --mode world --world-save .data/world/world.json --interval 1
```

Chaque tick représente une heure du monde. Pour une avance finie :

```bash
python main.py --mode world --world-save .data/world/world.json --ticks 24 --interval 0
```

Le programme recharge et sauvegarde l'état à chaque tick. Les PNJ se déplacent même sans action de joueur. Pour connecter une partie à cet état :

```bash
python main.py --interactive --save .data/adventure/player.json --world-save .data/world/world.json
```

Les écritures de l'état du monde sont verrouillées sur Linux et Windows, et les remplacements de fichiers sont atomiques. Le pilote du monde conserve les découvertes, recrutements et constructions enregistrés par la partie. La partie récupère la nouvelle horloge lors des observations, déplacements et sauvegardes. `attendre 4` avance également la simulation depuis le mode interactif.

Sans `--world-save`, l'état du monde reste inclus dans la sauvegarde du personnage. Les anciennes sauvegardes démarrent la simulation à leur heure enregistrée. Le moteur reste une application locale : le fichier de personnage garde un seul processus écrivain ; ce système ne fournit pas de comptes ou de serveur multijoueur.

## Ajouter des ressources

Ajouter des entrées dans `landmarks`, `sites`, `constructions`, `npcs` et `patrols`, ainsi que les zones nécessaires, dans un fichier JSON supplémentaire. Les repères référencent les zones, les sites les matériaux et les programmes de PNJ des chemins existants. Les patrouilles peuvent aussi parcourir les sentes hors route. Les programmes doivent être continus et revenir à leur point de départ. La validation contrôle les références, les niveaux, les populations, les coûts, les sites, les historiques d'itinéraires et les états sauvegardés. Les zones visibles restent accessibles par route ; les zones cachées peuvent dépendre uniquement des repères.
