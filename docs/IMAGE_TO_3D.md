# Outil local : images 2D vers modèles 3D

Double-cliquer sur `images-vers-3d.cmd` à la racine du projet. Choisir une image,
un dossier de sortie et une profondeur, puis cliquer sur **Créer les modèles 3D**.
Le bouton **Sprites du jeu** sélectionne le catalogue actuel. La case des poses
exporte chaque image d'animation dans son propre GLB.

L'outil fonctionne localement. Il accepte PNG, WebP, JPEG et les catalogues JSON
du jeu. Il produit des fichiers **GLB (glTF 2.0)** avec géométrie, normales et
couleurs, importables dans Blender et les moteurs compatibles avec GLB.

La forme est obtenue par extrusion arrondie de la silhouette : le centre est
plus épais que les bords. Les pixels transparents sont évidés, les faces internes
entre pixels voisins sont supprimées. Le résultat reste une silhouette en volume ;
il ne reconstruit pas les parties cachées d'un personnage ou d'une photo.
Un PNG à fond transparent donne le meilleur détourage. Un JPEG conserve son
fond rectangulaire, sauf retrait explicite d'une couleur exacte avec `--background`.

## Commandes PowerShell

```powershell
# Interface à double-clic, ou :
.\images-vers-3d.cmd

# Une image, avec une profondeur réglable :
.\images-vers-3d.cmd "C:\images\personnage.png" --depth 0.45 --output dist/mon-personnage

# Retirer un fond blanc uni :
.\images-vers-3d.cmd "C:\images\objet.png" --background "#ffffff"

# Toutes les entités du jeu et toutes leurs poses :
.\images-vers-3d.cmd projects/authored/content.json --all-frames --output dist/models_3d
```

Les images sont réduites à 64 pixels maximum sur leur plus grand côté avant
conversion. `--size 128` augmente la définition (maximum 256). Les sprites du
catalogue conservent leur résolution native, leurs teintes et leurs armes.
`--depth` règle l'épaisseur par rapport à une hauteur/largeur maximale de 1 unité.

Le fichier `manifest.json` associe chaque export à son entité, son sprite, sa pose
et sa durée. Les poses sont des modèles séparés ; elles ne constituent pas une
animation squelettique intégrée au GLB. Ces exports ne remplacent pas automatiquement
les modèles procéduraux actuellement affichés dans le jeu.

Les fichiers générés dans `dist/` sont locaux et exclus de Git. Relancer une
conversion dans le même dossier remplace les fichiers portant le même nom.
Sur une nouvelle installation, installer le supplément image :

```powershell
python -m pip install -e ".[art]"
```

## Vérification visuelle

```powershell
node scripts/preview_entity_sprites.cjs
node scripts/preview_entity_models.cjs
node scripts/preview_entity_models.cjs --converted
```

Les deux dernières commandes écrivent `.data/entity-models.png` et
`.data/converted-models.png`. Elles utilisent le Chromium local de l'environnement
de vérification du projet. La première affiche les sprites 2D actuels.

Validation de cette livraison : 388 GLB créés pour 97 entités et quatre poses,
contrôlés par le validateur Khronos glTF : **0 erreur, 0 avertissement**.
