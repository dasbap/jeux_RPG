# Rosée : quartiers et alentours

Le catalogue du Builder et celui du jeu contiennent **27 cartes**, contre 16
avant cette extension. Les cartes existantes conservent leurs identifiants.

## Village

La place de Rosée passe de 64 × 40 à **88 × 56 cases**, avec douze bâtiments,
des rues, une place centrale et une enceinte en pierre percée de portes.
Mira, Garrik et Sève gardent leurs positions et leurs quêtes.

Les passages donnent accès à des cartes distinctes :

- Au nord : cour de la caserne, maison des gardes et armurerie des chevaliers.
- Au nord-est : remparts et porte du Nord.
- À l'est : quartier des artisans, puis Prairies des Lucioles.
- Au sud : quartier des maisons, puis chemin vers Brume.
- À l'ouest : Forêt de Rosée, puis Forêt des Éveillés.

Chaque quartier possède une garnison de **deux chevaliers et un archer**.
L'archer tire jusqu'à six cases avec ligne de vue ; les chevaliers doivent
approcher au corps à corps. Leurs sprites affichent respectivement arc et
épée/bouclier. Tous les quartiers défendent le même village : ils ne créent pas
des raids ou économies supplémentaires. Pendant le siège de Rosée, leurs
patrouilles interrompent aussi le repli.

## Extérieurs

La zone **Forêts et vergers de Rosée** regroupe forêt, prairies, verger, bois,
Clairière des Sentinelles et Bois du Ruisseau. Les deux nouveaux secteurs
créent un chemin alternatif vers le Bois des Murmures.

La zone **Monts de Rosée** regroupe carrière, contreforts, Col des Guetteurs
et Tour des Cimes. On y accède par la porte du Nord ; le col rejoint aussi
la Lisière. Les nouveaux secteurs extérieurs ont leurs propres apparitions de
loups ou de kobolds, avec des niveaux progressifs.

Les quêtes qui ciblaient les monstres de l'ancienne zone générale de Rosée
ciblent maintenant leur zone forestière ou montagneuse correspondante.

## Sprites et sauvegardes

Les sprites animés se retournent **à gauche ou à droite** avec le déplacement
ou la cible. La direction est conservée à l'arrêt, séparément pour chaque
entité. Le corps et l'arme sont retournés ensemble ; les textes et les barres
de vie restent lisibles. Les images d'origine du Sprite Maker sont conservées.

La migration du monde vivant accepte explicitement le catalogue précédent
à vitesse normale. Elle conserve stocks, ressources, intégrité des villes,
raids, historique et échéances existantes, puis ajoute les nouvelles patrouilles.
Un catalogue inconnu reste refusé. Les soldats bloqués par un nouveau mur sont
repositionnés sans restaurer leurs PV. Le mécanisme de migration du terrain
existant repositionne aussi les personnages et conserve leur progression.

## Vérifications locales

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_rosee_expansion.py test/test_guard_patrols.py -q
.\.venv-reprise\Scripts\python.exe scripts/verify_living_world_browser.py --guards --rosee
node scripts/verify_sprites.cjs
```

Le scénario navigateur utilise une base temporaire, sans accès réseau externe.
Il vérifie Rosée, les sprites des deux rôles, le combat et le repli hors raid.
Les tests vérifient aussi l'accessibilité des passages, la séparation des zones,
la migration des sauvegardes et la défense commune du village.

L'extension initiale est décrite dans `scripts/expand_rosee.py`. Ce script refuse
de remplacer une extension déjà installée ; les retouches suivantes se font
dans le Builder.
