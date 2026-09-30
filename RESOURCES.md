# Ressources extensibles

`main.py` délègue le lancement à la CLI. La CLI et le moteur utilisent le catalogue ; les définitions ne sont plus inventées dans le lancement, le combat ou le craft.

Toutes les ressources du jeu sont livrées dans `jeuxRPG/resources/catalog.json` : emplacements, créatures et classes associées, tables de butin, matériaux, modèles d'armure, ingrédients des recettes, composition/bonus des panoplies, compétence de base et réglages de rang. Les classes de personnages et leurs compétences principales restent définies dans les modules Python existants du projet.

Les fichiers JSON placés **directement** dans `jeuxRPG/resources/` sont fusionnés au prochain démarrage. Les sous-dossiers d'exemples ne sont pas activés implicitement. On peut aussi choisir un autre fichier ou dossier :

```bash
python main.py --resources ./mes-ressources --save .data/personnage.json
```

Un dossier doit contenir un catalogue de base et ses extensions. Chaque identifiant ne peut être déclaré qu'une fois : pour ajuster une ressource existante, modifier sa définition. Les doublons, références absentes, ingrédients négatifs, plages de butin incohérentes et équipements incompatibles sont refusés avant le chargement d'une partie.

## Ajouter du contenu

Le fichier livré `jeuxRPG/resources/examples/spider.json` est un exemple complet. Il ajoute une araignée, sa soie, un emplacement d'épaulières, une armure, une recette et une panoplie. Il réutilise la classe de combat `Goblin` comme modèle ; il ne faut ajouter aucun cas particulier au moteur.

Pour l'essayer dans un dossier séparé :

```bash
mkdir mes-ressources
cp jeuxRPG/resources/catalog.json mes-ressources/00-core.json
cp jeuxRPG/resources/examples/spider.json mes-ressources/10-spider.json
python main.py --resources mes-ressources --interactive --save .data/araignee.json
```

Pour l'activer dans les ressources par défaut, copier l'exemple directement dans `jeuxRPG/resources/`. Une entrée JSON est découverte automatiquement au démarrage, sans modifier `Family`, `Slot`, `main.py`, `encounter` ou `auto_craft`. Les deux enums historiques restent disponibles uniquement pour compatibilité des appels Python existants.

| Section | Définition et références |
|---|---|
| `slots` | Identifiant d'emplacement → libellé affiché |
| `creatures` | Nom, `character_class`, module facultatif, liste de drops |
| `materials` | Identifiant `famille:type` → nom du matériau |
| `equipment` | Identifiant `famille:slot`, nom, famille, slot et bonus par rang |
| `recipes` | Même identifiant que l'équipement, équipement ciblé et quantités de matériaux |
| `sets` | Nom, liste d'équipements requis et bonus par rang |
| `skills` | Compétences de base disponibles dans l'arène |
| `rules` | Niveaux par rang et identifiant de compétence de secours |
| `character_modules` | Liste facultative de modules de nouvelles classes de personnages à importer |

Une nouvelle créature peut réutiliser une classe existante ou indiquer `module` avec un module du projet contenant une nouvelle sous-classe de `Character`. Le registre existant l'enregistre à l'import, sans modifier le point d'entrée. Les modules facultatifs doivent commencer par `jeuxRPG.`.

## Instances et règles communes

Les définitions sont préexistantes et validées. Le jeu crée des **instances** d'ennemis et d'objets à partir de ces définitions, comme toute partie RPG ; il n'écrit aucun nouveau fichier de catalogue pendant le lancement.

Les objets sont identifiés dans l'inventaire par `item-000001`, etc. Une recette de rang 2 se nomme par exemple `Spider:2:shoulders` ; elle référence le modèle `Spider:shoulders`. Un matériau de rang 2 se nomme `Spider:2:silk`, à partir du matériau déclaré `Spider:silk`. Les bonus sont multipliés par le rang, suivant les règles communes. Les ingrédients proviennent exactement de la recette déclarée.

Une panoplie peut contenir n'importe quel nombre de pièces sur des emplacements distincts. Les pièces requises doivent avoir le même rang. Le craft automatique utilise cette composition, et les bonus restent actifs si une pièce supplémentaire occupe un autre emplacement.

Les sauvegardes existantes gardent leurs identifiants et chargent les mêmes définitions. Il faut relancer une partie avec le catalogue contenant ses ressources : si une définition sauvegardée a été supprimée, le chargement échoue sans réinventer l'objet ni écraser la sauvegarde. Changer les bonus d'une définition applique le nouvel équilibrage lors du chargement ; les statistiques de base du personnage sont enregistrées séparément.

Ajouter du contenu avec ces mécanismes nécessite seulement des données ou une nouvelle classe enregistrée. Une mécanique de jeu entièrement nouvelle, comme la durabilité ou une nouvelle famille d'effets, demande naturellement une implémentation du moteur.

Les ressources comprennent désormais une carte multi-monde, les populations de zones, les chemins, les services, les sous-espèces et les boss. Leur schéma, les commandes et les plafonds de niveau sont décrits dans [WORLD.md](WORLD.md). Les nouvelles créatures peuvent déclarer `zones` pour rejoindre la population d'une zone existante via un fichier supplémentaire.

Les repères, sites stratégiques, chantiers, PNJ, patrouilles et programmes autonomes sont déclarés dans `frontier.json`. Voir [FRONTIER.md](FRONTIER.md) pour étendre l'exploration et la fondation de villages.
