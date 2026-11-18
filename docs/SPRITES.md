# Sprite Maker et entités

Le contrôleur du Builder possède un onglet **Sprites / Sprite Maker**. Il est
également accessible depuis la fenêtre d'édition des cartes ouverte par ce
contrôleur. Pour démarrer le Builder depuis la racine du dépôt :

```powershell
.\.venv-reprise\Scripts\python.exe -m jeuxRPG.multiplayer.controller projects/authored
```

## Dessiner et associer

1. Ouvrir le Sprite Maker. Choisir un sprite existant, **Nouveau**, ou
   **Modèle original** pour un voyageur ou une créature.
2. Dessiner au crayon. Le clic droit efface ; les outils proposent aussi gomme,
   remplissage et pipette. Une case grise représente un pixel transparent.
3. Choisir les couleurs, ajouter une couleur, retourner horizontalement le dessin,
   ou annuler/rétablir un trait. Les nouvelles grilles font 8, 16, 24 ou 32 pixels.
4. Dupliquer une image pour créer une animation, puis régler sa durée et regarder
   l'aperçu. Chaque sprite contient jusqu'à huit images. Les images représentent
   pour l'instant une boucle unique, sans sélection automatique d'une direction.
5. Donner un identifiant et un nom, puis **Appliquer le sprite au projet**.
6. Choisir l'entité dans **Associer un sprite à une entité**, sélectionner le
   sprite et appliquer l'association. **(Aucun)** retire une association.
7. Dans le contrôleur, **Enregistrer le projet** écrit les changements sur disque.
   Les boutons généraux Annuler/Rétablir prennent en compte sprites et associations.

Les associations couvrent une classe de personnage, une espèce de monstre, un
PNJ/lieu nommé, ou un type d'acteur ambiant : habitants, gardes, groupes de monstres,
caravane et assaillants. Une association de classe s'applique aux personnages de
cette classe ; elle ne choisit pas encore un portrait individuel par joueur.
Les entités sans association gardent leurs marqueurs habituels. Les noms,
sélections, déplacements et interactions restent disponibles sur la carte.

Renommer un sprite dans le Maker réaffecte ses associations. Le supprimer demande
confirmation et retire ses associations. Supprimer une entité référencée demande
d'abord de retirer son association ; la validation signale la référence manquante.
Si un sprite est modifié dans le projet complet JSON ou via l'annulation globale,
recharger ce sprite dans le Maker avant de poursuivre le dessin.

## Corps partagé, arme et teinte

Le pack local couvre les **91 entités existantes** : classes, espèces de monstres,
PNJ/indices et acteurs ambiants. Il contient **47 assets animés**, dont onze armes,
avec quatre images par animation. Les animaux, insectes, volants, slimes,
squelettes, golems, plantes et humanoïdes utilisent des silhouettes adaptées.
Les variantes d'une même famille réutilisent leurs corps et leurs images.

Exemple : `goblin`, `gobelin_archer`, `garde_gobelin`, `gobelin_chamane` et les
autres gobelins utilisent `gobelin_original`. Leurs associations choisissent
respectivement une lance, un arc, une épée avec bouclier, un bâton, etc.
Un changement d'arme ne copie et ne modifie pas les pixels du corps.
Les slimes bleus et verts partagent aussi leur animation, avec une teinte différente.

Dans **Associer un sprite à une entité**, choisir le **corps**, puis le **calque
d'arme**, et éventuellement une **teinte du corps**. Appliquer l'association puis
enregistrer le projet. Le dessin de base reste inchangé lorsque l'on change la
teinte ; la teinte modifie sa couleur principale et son éclaircissement.
L'association d'arme est visuelle : les statistiques et compétences restent celles
de la définition de l'entité.

Les espèces `gobelin_archer` et `squelette_archer` possèdent désormais une attaque
de base **Tir de flèche**, de portée maximale **6 cases**. La préparation et la
cadence restent celles du moteur de combat. Distance et ligne de vue sont
revérifiées au moment de la résolution : une cible hors de portée ou derrière une
couverture ne reçoit pas le tir. La portée et le nom de l'attaque se règlent dans
la fiche d'espèce du Builder et apparaissent dans le bestiaire. Les anciennes
parties reçoivent ces réglages lorsqu'ils sont absents, sans modifier les PV.

Le bouton **Gabarit arme 24 × 24** crée un calque transparent. Le repère jaune
indique la main près du pixel `(18, 14)` ; le rectangle guide marque la zone droite
prévue pour l'arme. Le bouclier peut occuper la partie gauche du calque.
Corps et arme doivent avoir les mêmes dimensions ; l'aperçu montre la composition.
Les calques du pack ont les mêmes quatre poses et la même durée de 180 ms pour
rester alignés. En éditant une animation, conserver ces poses et durées sur ses
armes compatibles. Il s'agit de boucles visuelles ; les animations directionnelles
et les séquences propres à chaque compétence ne sont pas encore distinctes.

Le jeu compose les deux calques dans une seule image mise en cache. Les mêmes
compositions sont affichées sur les cartes et dans les fiches du bestiaire.

## PNG et format du projet

L'import accepte un PNG d'au plus 32 × 32 pixels. Il conserve la transparence et
ramène les couleurs à une palette de quinze couleurs dominantes plus le transparent.
Vérifier le résultat avant application, notamment pour un dessin avec dégradés.
L'export PNG écrit uniquement l'image actuellement sélectionnée, avec transparence.
Toutes les images d'animation restent conservées dans le projet JSON.

Les pixels sont intégrés dans `content.json`, section `content.sprites` :
`assets` contient les palettes et images ; `bindings` associe une clé d'entité
(`class:Knight`, `mob:goblin`, `npc:mira`, `ambient:guards`, etc.) à un identifiant
de corps. `equipment` associe ces mêmes clés aux calques d'armes ; `colors` contient
les teintes facultatives. Un asset peut déclarer `layer: "body"` ou
`layer: "weapon"`. Les anciens sprites sans calque explicite restent des corps.
Il n'y a ni adresse d'image distante, ni fichier privé à copier.
Le format impose des limites de dimensions, images, couleurs et taille totale.
Le catalogue ne peut pas contenir du HTML, du SVG importé ou un script.

Le rendu du jeu fabrique des images SVG depuis les seuls pixels validés. Les
images sont partagées en cache entre les entités et les animations ne nécessitent
aucune requête réseau. Les sprites sont inclus dans le moteur solo et les assets
du build Windows. Après une modification, reconstruire le client local pour
l'intégrer au `.exe` ; une partie solo existante n'a pas besoin d'être effacée.
Pour un serveur Python local, redémarrer le serveur avec le catalogue actualisé.

## Modèles originaux fournis

Les dessins du pack ont été écrits pour ce projet, sans recopier de pack graphique
tiers. Ils sont tous modifiables dans le Maker. Le générateur source est
`jeuxRPG/multiplayer/entity_sprite_art.py` ; il produit des pixels, sans modèle
externe, téléchargement ou dépendance graphique supplémentaire.

Les dessins initiaux `chevalier_original`, `garde_original`, `marchand_original`
et `gobelin_original`, les assets `corps_*`, `arme_*` et `objet_*` du pack, ainsi
que les deux formes du bouton **Modèle original**,
sont fournis sous **CC0 1.0** : utilisation, modification et redistribution
permises, y compris commerciales, sans attribution obligatoire.
Référence : https://creativecommons.org/publicdomain/zero/1.0/
Cette indication concerne ces dessins nouveaux, pas les autres contenus du dépôt.
Les images importées conservent la licence choisie par leur auteur.

Pour régénérer le pack local :

```powershell
.\.venv-reprise\Scripts\python.exe -m scripts.generate_entity_sprites
```

Cette commande réécrit les dessins et associations gérés par le pack dans
`projects/authored`, puis enregistre le projet. Les assets personnalisés portant
d'autres identifiants sont conservés ; les associations des entités existantes
sont remises aux choix du pack.

Pour actualiser uniquement les dessins gérés en conservant les associations,
armes et teintes personnalisées, ajouter `--art-only` :

```powershell
.\.venv-reprise\Scripts\python.exe -m scripts.generate_entity_sprites projects/authored --art-only
```

Les surfaces de couleur principale reçoivent un éclaircissement en haut à gauche
et une ombre en bas à droite. L'index 14 du pack contient cette ombre, calculée à
65 % de la couleur principale ; le jeu et le Maker la recalculent lors d'une teinte.
Les anciens dessins dont l'index 14 utilise une autre couleur restent compatibles.

## Vérifier localement

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_sprites.py test/test_entity_sprite_art.py -q
node scripts/verify_sprites.cjs
node scripts/verify_desktop.cjs --packaged
node scripts/preview_entity_sprites.cjs
```

Les tests couvrent les données invalides, le budget, les coups de pinceau,
le remplissage, les images d'animation, l'annulation, les PNG transparents,
les associations, le renommage, la sauvegarde et la réouverture du projet.
La galerie locale est enregistrée dans `.data/entity-sprites.png`.
Les tests vérifient aussi la couverture de toutes les entités, le partage des
corps gobelins, les armes, les teintes, les dimensions des calques et leur renommage.
La vérification du client compilé contrôle le décodage du sprite hors ligne,
sa sélection et la reprise du solo. Aucun push ni activation distante n'est requis.
