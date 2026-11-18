# Grotte des Oubliés et atlas

Le donjon contient douze cartes physiques (`cave_1`, `cave_3` à `cave_12`, puis
`cave_2`, salle du chef). Vingt et un passages réciproques forment dix boucles.
Les directions des arches sont volontairement désaccordées : une sortie nord
peut déboucher par l'est. Toutes les salles restent accessibles et les retours
restent ouverts. Le plus court chemin de l'entrée au chef traverse six passages.
Les arrivées se font à deux cases des portes pour éviter un retour immédiat.

Chaque salle contient trois groupes d'ennemis : gobelins de mêlée, archers,
chamanes, chauves-souris, squelettes, golems, scorpions ou liches. Le niveau est
explicitement fixé entre 10 et 15 et augmente avec la distance depuis l'entrée.
Le chef gobelin est niveau 15. Les deux accès extérieurs gardent leurs
identifiants et positions pour conserver les liaisons avec la forêt et la lisière.

Toutes les salles utilisent le biome `cave` : parois rocheuses, bassins,
cristaux lumineux, foyers chauds et brume souterraine en 3D. Les couloirs,
arrivées et apparitions restent praticables.

Les sept régions ont un placement global explicite. Les quartiers de Rosée
suivent leurs portes cardinales, les secteurs forestiers et montagneux suivent
leurs passages, et Brume possède deux chaînes de rues distinctes. Les salles du
labyrinthe ont un plan volontairement croisé et des numéros pour les reconnaître.
Les noms longs des points sont répartis sur plusieurs lignes. Les chemins
à sens unique sont affichés même si leur origine suit leur destination dans
l'ordre alphabétique ; les liaisons réciproques sont dessinées une seule fois.

Les positions des points appartiennent au `world_view` de leur zone logique,
modifiable dans le Builder. Les anciennes surcharges de cartes ont été retirées.
`projects/authored/` reste la source ; `jeuxRPG/maps/` est l'export validé.

Pour reconstruire le contenu géré (écrase les retouches manuelles correspondantes) :

```powershell
python -m scripts.rework_world_maps
python -m scripts.export_builder_project
```

`refine_forgotten_cave.refine` construit le terrain et les passages du donjon ;
`rework_world_maps.arrange` place les régions et leurs points dans l'atlas.

Vérifications :

```powershell
python -m pytest -q test/test_forgotten_cave.py test/test_authored_project.py test/test_map_links.py test/test_map_layout_editor.py
python -m scripts.verify_cave_browser
```

Le scénario navigateur utilise une base temporaire et le vrai client WebGL.
Il vérifie l'entrée, une nouvelle salle, le chef, le retour à la forêt,
les douze points de l'atlas et leurs liaisons, Rosée et le rendu mobile.
Captures : `.data/forgotten-labyrinth-atlas.png`, `.data/rosee-atlas.png`
et `.data/cave_*-3d*.png`.
