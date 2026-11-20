# Vérification locale des sprites et de l'outil 2D vers 3D

Date : 17 novembre 2026.

## Correspondance des entités

Le catalogue comporte 47 assets et 97 associations : 58 monstres, 13 classes,
19 PNJ/lieux et 7 catégories ambiantes. Le projet éditable et le catalogue livré
ont été synchronisés et validés avec `Project.validate()`.

Corrections : silhouette propre aux reptiles 2D ; formes 3D pour rats, oiseaux,
insectes, scorpions, plantes, champignons, golems et spectres ; armes différenciées ;
les armes et teintes suivent désormais la même association que le corps en 2D
et 3D. Un effet de combat ne bloque plus une créature dépourvue de `combat_id`.

Les planches locales sont `.data/entity-sprites.png`, `.data/entity-models.png`
et `.data/converted-models.png`.

## Résultats

- 49 tests Python ciblant les sprites, la conversion, les compétences et les
  effets de combat : succès.
- 29 contrôles JavaScript des sprites, modèles, commandes et déplacements : succès.
- 388 exports GLB, correspondant à quatre poses pour chacune des 97 entités :
  validateur Khronos glTF, zéro erreur et zéro avertissement.
- Conversion d'un PNG par `images-vers-3d.cmd` et initialisation de l'interface Tk : succès.
- Ruff : lint et formatage du moteur Python conformes.

La suite Python complète lancée pendant la vérification a donné 2113 succès,
9 exclusions et 7 échecs. L'échec de compétence dû à `combat_id` a été corrigé
puis retesté avec succès. Les six autres échecs sont confirmés dans :

- `test_builder_world_topology.py` (2 tests) ;
- `test_builder_zone_views.py` (1 test) ;
- `test_logical_zones.py` (1 test) ;
- `test_region_extensions.py` (2 tests).

Ces tests attendent encore les anciens regroupements de zones, durées et nombres
de cartes, alors que le répertoire contenait déjà l'expansion de Rosée avant
cette intervention. Leurs attentes n'ont pas été modifiées ici.

Le scénario navigateur `verify_living_world_browser.py --3d` atteint le rendu
WebGL et valide une réponse visuelle en 105 ms, puis échoue sur son assertion de
position serveur après une avance d'horloge de fixture. La validation des modèles
seuls a été effectuée séparément dans Chromium avec un rendu WebGL sans erreur.

Les modifications déjà présentes ont été conservées dans un commit local,
avec les corrections des sprites ; le convertisseur fait l'objet d'un second
commit local. Aucun push ni déploiement n'a été demandé ou exécuté.
