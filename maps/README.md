# Cartes du jeu

Les terrains du jeu sont stockés dans les fichiers JSON de ce dossier. Le moteur charge le catalogue au démarrage ; les fichiers Python ne définissent plus les cartes fixes ou les presets de rencontre.

- `world.json` : cartes fixes et leurs passages, décors, apparitions et PNJ.
- `encounters.json` : quinze terrains de rencontres rapides, avec `kind: encounters`.

Les cartes fixes peuvent être réparties entre plusieurs fichiers JSON contenant chacun un dictionnaire de cartes. Chaque identifiant doit apparaître une seule fois dans le dossier. Ne pas ajouter un export complet à côté du fichier original : cela dupliquerait les identifiants.

Le builder ouvre `maps/world.json` par défaut lorsqu’il est lancé depuis le dépôt. Enregistrer remplace ce fichier. Pour un catalogue découpé, ouvrir les cartes via `python map_editor.py maps`, puis enregistrer un export complet dans un fichier situé hors du catalogue d’origine et charger cet export via `RPG_MAPS_FILE`.

Pour utiliser directement les JSON du dépôt dans PowerShell :

```powershell
$env:RPG_MAPS_FILE = (Resolve-Path .\maps).Path
python main.py
```

Sans variable, le jeu charge les JSON fournis avec le paquet installé. Après modification du dépôt, réinstaller avec `python -m pip install --upgrade .` ou utiliser la variable ci-dessus.

## Les trois secteurs de départ

| Identifiant | Carte | Particularité |
| --- | --- | --- |
| `clearing` | Sentier oublié | Terrain repris de la référence inachevée, sentier irrégulier, rivière oblique et premier gobelin |
| `clearing_trail` | Vieux pont | Forêt plus dense, sentier prolongé et traversée du cours d’eau |
| `clearing_road` | Route entretenue | Chemin large, continu et en bon état ; sortie vers le voyage rapide de Rosée |

Chaque secteur mesure 30 × 20 cases. Leurs origines globales sont `[0,0]`, `[26,0]` et `[52,0]`. Les quatre dernières colonnes d’un secteur correspondent aux quatre premières du suivant : terrain, obstacles, eau, ponts, chemin et décor sont identiques dans cette bande commune.

Les passages transportent le groupe vers une case située après la bande commune ; les retours sont disponibles. Ces secteurs appartiennent à la même zone logique `clearing`. Seule la route entretenue rejoint la vue générale. Après cette sortie, explorer à nouveau ramène à l’extrémité de cette route.

Les champs `world_origin` et `overlap_columns` décrivent le raccord. Modifier un bord commun dans le builder ne synchronise pas automatiquement la carte voisine : reporter les changements dans les deux fichiers de données avant de sauvegarder.

L’eau bloque les déplacements mais laisse passer la vue ; les ponts sont praticables. Les arbres et les rochers bloquent déplacement et vue.

[Vue d’ensemble des trois secteurs](../docs/STARTING_MAPS.svg)

[Guide complet du builder](../docs/BUILDER_GUIDE.md)

## Zones, spawners et fortifications — alpha 0.11.0a5

`mobs.json` est un catalogue `kind: mobs`, distinct des cartes. Il contient les espèces gobelin, orc et dragonnet utilisées par les spawners. Les cartes disposent de `zone_id`, `zone_level` et d’une éventuelle surcharge `level`. Chaque entrée de `spawners` correspond à une case de `spawns`, avec une espèce `mob_id`, un niveau facultatif, un groupe `count` et une patrouille facultative `patrol`.

Les décors `barricade` et `wall` doivent aussi figurer dans `cover` pour bloquer le déplacement et la vue. Le builder le fait automatiquement. Le campement gobelin fourni comporte des remparts et des murs, avec des passages praticables.

Le bouton Synchroniser les raccords copie maintenant le terrain et le décor dans les bandes communes, sans déplacer les entités ou modifier les passages. Valider les cartes après cette opération.
