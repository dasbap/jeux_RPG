# Armes de classe

La forge propose quatre armes, avec un emplacement **Arme** distinct des six
emplacements d'armure. Leur fabrication équipe directement la nouvelle arme ;
l'ancienne est conservée en réserve. L'inventaire et le menu Équipement permettent
de les équiper et déséquiper dans les mêmes conditions que les autres pièces.

| Recette | Classes compatibles | Bonus de base |
| --- | --- | --- |
| Épée de la Lisière | Chevalier | +3 force, +1 endurance |
| Arc des Ronces | Archer | +4 force, +1 endurance |
| Bâton des Lucioles | Mage, Prêtre, Nécromancien | +3 intelligence, +3 sagesse |
| Sceptre de la Veille | Mage, Prêtre, Nécromancien | +5 intelligence, +5 sagesse |

La forge de Rosée conserve son déblocage auprès de Mira. Le filtre **Votre classe**
montre les recettes compatibles ; **Toutes les classes** affiche aussi les armes
incompatibles avec leur liste de classes et un bouton désactivé. Les mêmes classes
apparaissent sur les armes de l'inventaire et de l'équipement.

Le moteur vérifie ces restrictions à la fabrication, à l'amélioration et à
l'équipement, avant toute consommation de matériaux ou application de bonus.
Une arme partagée utilise la même recette pour toutes ses classes compatibles.
Les armes s'améliorent indépendamment ; améliorer une arme en réserve n'applique
pas ses bonus au personnage. Les anciens équipements d'armure restent universels.

En 2D et en 3D, l'arme équipée remplace le visuel d'arme de la classe ; son corps et
sa teinte restent ceux de cette classe. En 2D, le remplacement utilise un calque
existant de dimensions compatibles. Retirer une arme fabriquée restaure le visuel
de base de la classe.

Dans le Builder, **Forge / recettes** contient les champs `weapon_type` (sword,
bow, staff) et une liste `classes`. La liste permet plusieurs classes par arme.
Les classes inconnues, doublons, listes vides d'arme et types invalides sont refusés.
Si le Builder retire une classe autorisée à une arme déjà équipée, celle-ci passe
en réserve et ses bonus sont retirés une seule fois, sans perte de l'objet.

Les définitions sont dans `projects/authored/content.json`, exportées vers
`jeuxRPG/maps/content.json`. Le script `python -m scripts.add_class_weapons`
reconstruit ces quatre recettes ; l'export passe par `python -m scripts.export_builder_project`.
Le transport des états transmet le déblocage de la forge et les noms de matériaux
pour garder les boutons et les coûts cohérents avec le moteur.

Validation :

```powershell
python -m pytest -q test/test_class_weapons.py test/test_equipment_management.py test/test_equipment_sets.py test/test_controller_gameplay.py test/test_state_bundles.py
node --test scripts/verify_equipment_ui.cjs scripts/verify_scene3d.cjs scripts/verify_sprites.cjs
python -m scripts.verify_equipment_browser --weapons
```

Le scénario navigateur réalise une fabrication via l'API d'une base temporaire,
vérifie les coûts, un refus de classe, l'équipement et sa persistance après
rechargement. Captures sous `.data/weapons-*.png`.
