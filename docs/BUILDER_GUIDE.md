# Guide complet du builder de cartes RPG

Version : alpha 0.11.0a5.

Le builder est un éditeur de bureau indépendant du jeu. Il permet de modifier les cartes fixes, leur décor, les spawners de créatures, les passages et les PNJ. Les modifications sont enregistrées dans un fichier JSON choisi par l’utilisateur, puis chargées par le serveur à son démarrage.

## 1. Installer et lancer

Depuis le dossier du dépôt, dans PowerShell :

```powershell
git pull origin codex/secure-multiplayer-poc
python -m pip install --upgrade .
python map_editor.py
```

Pour ouvrir directement un fichier existant :

```powershell
python map_editor.py .\maps.json
```

Autres commandes disponibles après installation :

```powershell
python -m jeuxRPG.multiplayer.map_editor
jeux-rpg-map-editor
```

L’éditeur utilise Tkinter. L’installation officielle de Python sous Windows doit inclure Tcl/Tk. Sur Linux, installer le paquet Tkinter adapté à la distribution. Le builder ne nécessite pas de serveur de jeu actif.

## 2. Choisir une carte et lire l’écran

La liste supérieure affiche `Nom de la carte [identifiant]`. Choisir une ligne pour travailler sur cette carte.

Le nom affiché peut changer. L’identifiant entre crochets est une référence stable utilisée par les passages ; modifier le nom ne renomme pas cet identifiant.

- À gauche : outils de terrain et d’entités.
- Au centre : grille de la carte.
- En haut : fichiers, annulation, création de carte et propriétés.
- En bas : identifiant, coordonnées sous la souris, outil actif et chemin du fichier.

Les coordonnées commencent à `0,0` dans le coin supérieur gauche. `x` augmente vers la droite, `y` vers le bas. Une carte de 30 × 20 cases va de `0,0` à `29,19`.

Les boutons `−` et `+` changent la taille des cases. Les barres de défilement horizontale et verticale permettent de parcourir les grandes cartes.

### Symboles

| Symbole | Objet |
| --- | --- |
| G, O, D rouges | Spawner de gobelin, orc, dragonnet |
| X, M | Rempart de fortune, mur |
| ↗ bleu | Passage ou sortie |
| N jaune | PNJ fixe |
| P jaune | PNJ lié à un joueur |
| ♣, ◆, ⌂ | Arbre, rocher, maison |
| ✿, ⁙, ✦, ▲ | Fleurs, herbe, cristal, campement |

## 3. Modifier le nom, les dimensions et l’ambiance

Sélectionner la carte puis cliquer sur **Propriétés carte**.

| Champ | Utilisation |
| --- | --- |
| Nom affiché | Nom présenté dans l’éditeur et dans les vues du jeu correspondant à cette carte |
| Largeur (cases) | Entier de 4 à 128 |
| Hauteur (cases) | Entier de 4 à 128 |
| Ambiance | `forest`, `village` ou `cave` |

Valider applique les changements au document ouvert. Il faut encore enregistrer le fichier et redémarrer le serveur pour les voir en jeu.

Réduire les dimensions ne supprime pas automatiquement les objets hors limites. Déplacer ou effacer les objets concernés avant d’enregistrer. La validation signale les cases hors carte.

## 4. Créer une nouvelle carte

Cliquer sur **Nouvelle carte** puis donner un identifiant unique, composé de lettres minuscules, chiffres et underscores, par exemple `jardin_rosee`.

La carte créée mesure 30 × 20 cases et comporte une sortie vers les chemins rapides. Modifier son nom et ses dimensions dans les propriétés, puis construire son terrain.

Pour y accéder depuis le jeu, ajouter un passage depuis une carte existante. Une nouvelle carte n’ajoute pas automatiquement un itinéraire de voyage rapide au graphe du monde.

Les sept cartes de référence du tutoriel doivent rester dans le fichier : `clearing`, `rosee`, `lisiere`, `hunt`, `forest`, `cave_1`, `brume`. Les salles `cave_2` et `cave_3` peuvent être absorbées par fusion.

## 5. Peindre le terrain

Choisir un outil puis cliquer sur une case. Maintenir le bouton et glisser pour peindre plusieurs cases. Un clic suivi d’un glisser constitue une opération annulable avec **Annuler** ou `Ctrl+Z`.

| Outil | Déplacement | Ligne de vue |
| --- | --- | --- |
| Sol | Praticable | Transparente |
| Arbre, Rocher, Maison, Rempart X, Mur M | Bloqué | Bloquée |
| Eau | Bloqué | Transparente |
| Pont | Praticable | Transparente |
| Chemin | Praticable | Transparente |
| Fleurs, Herbe, Cristal, Camp | Praticable | Transparente |

Peindre une case remplace son ancien terrain et son ancien décor. Cela ne supprime pas les PNJ, passages ou apparitions déjà placés dessus. La sauvegarde refuse qu’un obstacle recouvre une apparition, un PNJ ou un passage.

Pour une rivière : peindre les cases avec **Eau**, puis placer **Pont** aux traversées souhaitées. Les arbres, rochers et maisons sont des obstacles par case, pas des bâtiments avec un intérieur automatique.

**Effacer** retire le terrain, le décor, les passages, les PNJ et les apparitions de la case. **Sol** nettoie uniquement le terrain et le décor.

## 6. Placer et modifier une téléportation

Choisir **Téléportation**, puis cliquer sur une case libre. Pour modifier un passage existant, cliquer sur sa case avec le même outil.

| Option | Utilisation |
| --- | --- |
| Nom affiché | Libellé du passage |
| Carte destination | Identifiant de la carte cible ; la liste propose les cartes du fichier |
| Case d’arrivée x,y | Case où le groupe apparaît dans la destination, par exemple `2,10` |
| Provenance du chemin rapide | Carte d’origine associée à une sortie complète ; aide à choisir le passage lors d’une arrivée par voyage rapide |
| Créer aussi le passage de retour | Ajoute dans la destination un passage vers la carte source |

### Passage entre deux cartes

Sélectionner une destination et renseigner une case d’arrivée praticable. L’arrivée doit être différente des cases de passage déjà présentes dans la destination, pour éviter un aller-retour automatique en boucle.

Le passage se déclenche lorsque le joueur marche sur sa case. Il transporte le groupe. Les ennemis qui ont vu la sortie peuvent poursuivre selon les règles du jeu.

### Passage aller-retour

Cocher **Créer aussi le passage de retour**. Le builder cherche une case libre voisine de l’arrivée pour le passage inverse, et une case libre voisine du passage source pour le retour du groupe.

Les deux cartes doivent disposer de ces cases libres. Sinon, le formulaire affiche une erreur et ne pose aucun des deux passages. Le retour automatique exige deux cartes différentes.

Le passage inverse porte le nom `Retour vers …`. Il est ensuite éditable avec l’outil Téléportation sur la carte destination. Supprimer un passage avec Effacer ne supprime pas automatiquement son inverse : retirer les deux si nécessaire.

### Sortie complète vers les chemins rapides

Laisser **Carte destination** vide. Le groupe quitte la carte locale et revient à la vue générale ; les ennemis ne poursuivent plus.

La case d’arrivée n’est pas utilisée pour cette sortie. **Provenance du chemin rapide** est facultative : elle sert à associer ce passage à la carte d’où vient un voyage rapide. Elle ne crée pas une nouvelle route et ne choisit pas une destination de voyage à votre place.

Le retour automatique n’est pas disponible pour une sortie complète.

## 7. Ajouter des spawners

Choisir **Spawn**, puis cliquer sur une case praticable. Cliquer à nouveau sur cette case avec le même outil pour modifier son spawner.

| Champ | Utilisation |
| --- | --- |
| Espèce | `goblin`, `orc`, `dragon_whelp` |
| Niveau local | Vide : hériter du niveau de la carte ; entier 1–100 : niveau propre au spawner |
| Nombre de créatures | 1 à 5 créatures présentes simultanément |
| Nom affiché | Nom facultatif des créatures de ce spawner |

Chaque spawner peut choisir une espèce différente. Une carte accepte au maximum 64 spawners et 128 créatures au total. Le groupe utilise des cases voisines praticables distinctes autour du point d’apparition. Les statistiques du personnage sont augmentées au niveau choisi ; les attaques ennemies restent pilotées par l’IA tactique commune. Le catalogue `maps/mobs.json` définit les espèces disponibles, leurs classes du moteur, rangs, dégâts et matériaux. Les trois espèces utilisent actuellement les matériaux communs `peau` et `croc` de la forge.

Les anciens points d’apparition sans configuration détaillée restent des gobelins. Le repop conserve l’espèce, le niveau, le groupe et la patrouille configurés. Tester une nouvelle session après une modification pour ne pas conserver les anciennes créatures sauvegardées.

### Dessiner une patrouille

1. Choisir **Patrouille** et cliquer sur le spawner.
2. Accepter le remplacement des points pour repartir de zéro ; refuser pour continuer la patrouille existante.
3. Cliquer successivement sur les cases à parcourir. Les numéros affichent l’ordre.
4. Cliquer sur **Fin patrouille**.

Une patrouille contient au maximum 32 points accessibles. Les créatures passent de point en point et recommencent le parcours. Sans point personnalisé, elles utilisent la patrouille automatique du moteur. La poursuite et les recherches prennent la priorité sur la patrouille.

## 8. Ajouter un PNJ

Choisir **PNJ**, puis cliquer sur une case libre. Cliquer à nouveau sur sa case avec cet outil pour modifier ses propriétés.

| Champ | Utilisation |
| --- | --- |
| Identifiant PNJ | Référence unique dans la carte, par exemple `guide_foret` |
| Nom affiché | Nom du personnage |
| Dialogue | Texte renvoyé lors d’une interaction à proximité |
| Joueur lié | Vide : PNJ fixe ; `leader` : premier joueur du groupe ; identifiant joueur : propriétaire précis |

Les PNJ liés suivent leur propriétaire et accompagnent le groupe entre les zones. Le propriétaire doit être présent et vivant. Les PNJ personnalisés sont pacifiques ; ils ne disposent pas encore d’une IA de combat ou d’un générateur de quêtes.

Ne pas réutiliser les identifiants `mira` et `forge` pour un nouveau personnage : ils sont utilisés par les interactions du tutoriel. Les PNJ d’escorte devraient avoir des identifiants distincts dans toutes les cartes pour éviter des collisions lorsqu’ils accompagnent le groupe.

Les invocations sont créées par les compétences en jeu, pas par l’outil PNJ. Sans cible ni contrôle manuel, elles suivent aussi leur propriétaire.

## 9. Inspecter, corriger et enregistrer

**Inspecter** affiche les données des objets de la case. Pour changer leurs propriétés, utiliser Téléportation ou PNJ plutôt qu’Inspecter.

- **Annuler** ou `Ctrl+Z` : revient sur les dernières modifications, dans la limite de 30 opérations.
- **Enregistrer** ou `Ctrl+S` : écrit le fichier courant ; demande un chemin à la première sauvegarde.
- **Enregistrer sous** : écrit dans un autre fichier.
- **Ouvrir** : charge un fichier validé. Enregistrer les modifications en cours avant d’ouvrir un autre fichier.

La fermeture de la fenêtre demande confirmation si des modifications ne sont pas enregistrées.

La sauvegarde valide notamment les dimensions, coordonnées, destinations, cases d’arrivée, obstacles, identifiants des PNJ et l’accessibilité des passages, PNJ et apparitions. Elle remplace le fichier seulement après une validation réussie.

## 10. Charger le résultat dans le jeu

Enregistrer dans `maps.json`, arrêter le serveur puis lancer dans PowerShell :

```powershell
$env:RPG_MAPS_FILE = (Resolve-Path .\maps.json).Path
python main.py
```

La variable doit être définie dans le terminal qui lance le serveur. Le serveur recharge le fichier à chaque démarrage, pas en direct pendant l’édition.

Tester avec une nouvelle session pour voir l’ensemble des nouvelles apparitions et interactions. Les sessions existantes conservent les ennemis, compagnons et zones explorées sauvegardés ; leurs positions devenues impraticables sont replacées après une modification de géométrie.

Pour revenir aux cartes intégrées :

```powershell
Remove-Item Env:RPG_MAPS_FILE -ErrorAction SilentlyContinue
python main.py
```

## 11. Exemple : relier Rosée à un jardin

1. Créer `jardin_rosee` et lui donner le nom « Jardin de Rosée ».
2. Peindre son décor en gardant des chemins praticables.
3. Choisir une case d’arrivée libre, par exemple `2,10`.
4. Revenir à Rosée et choisir une case libre pour le passage.
5. Avec Téléportation, nommer le passage « Jardin », choisir `jardin_rosee`, saisir `2,10` et cocher le retour automatique.
6. Dans le jardin, placer un PNJ `guide_jardin` avec dialogue et `leader` comme joueur lié.
7. Enregistrer, charger le fichier et démarrer une nouvelle session.
8. Marcher sur le passage dans Rosée, vérifier l’arrivée, le suivi du guide et le passage de retour.

## 12. Résoudre les problèmes courants

| Problème | Vérification |
| --- | --- |
| Je vois toujours l’ancien nom | Mettre à jour le paquet, enregistrer le bon fichier, définir RPG_MAPS_FILE puis redémarrer le serveur |
| Le nom entre crochets ne change pas | Il s’agit de l’identifiant stable ; le nom affiché se modifie dans Propriétés carte |
| Une option TP manque | Mettre à jour vers 0.11.0a3 ou ultérieur ; les options sont proposées aussi pour les anciens passages |
| Arrivée sur un obstacle ou hors carte | Choisir une case de sol, pont ou chemin dans les limites de la destination |
| Boucle de téléportation | Choisir une arrivée voisine du passage plutôt que sa case exacte |
| Retour automatique impossible | Libérer une case voisine de chaque extrémité ; vérifier que les destinations sont différentes |
| Point inaccessible | Ouvrir un chemin ou ajouter un pont ; le moteur interdit la traversée diagonale des coins d’obstacles |
| Objets hors carte après redimensionnement | Rétablir temporairement les dimensions, retirer les objets concernés, puis réduire la carte |
| Le PNJ ne suit pas | Vérifier son joueur lié, l’identifiant du joueur et sa présence dans le groupe |
| Les gobelins n’ont pas changé | Tester dans une nouvelle session ; les anciennes zones sont sauvegardées |
| Tkinter ne démarre pas | Vérifier l’installation Tcl/Tk et la présence d’un affichage de bureau |

Le builder ne modifie pas les tables de classes, les compétences ou le graphe des routes rapides. Il permet de régler la difficulté des cartes via les niveaux et les spawners.

## 13. Catalogue JSON du dépôt — alpha 0.11.0a4

Les cartes ne sont plus définies dans le code Python. Le dossier `maps/` contient `world.json` pour les cartes fixes et `encounters.json` pour les terrains de rencontres rapides. Le builder lancé depuis le dépôt ouvre et enregistre `maps/world.json` par défaut.

Pour un dossier de cartes fixes réparties entre plusieurs JSON, chaque identifiant doit être unique. On peut charger le dossier avec `python map_editor.py maps`. Enregistrer ensuite l’export complet dans un autre fichier, hors du catalogue initial, puis charger cet export dans le jeu. Ne pas laisser un export complet à côté des fichiers qui contiennent déjà les mêmes cartes.

Le serveur accepte aussi un dossier dans `RPG_MAPS_FILE` :

```powershell
$env:RPG_MAPS_FILE = (Resolve-Path .\maps).Path
python main.py
```

Les trois secteurs initiaux sont `clearing`, `clearing_trail` et `clearing_road`. Leurs quatre colonnes communes sont identiques ; les passages permettent d’avancer et de revenir. Seul le dernier secteur rejoint les chemins rapides. Les champs `world_origin` et `overlap_columns` gardent la référence du chevauchement. Le builder conserve ces champs, mais ne synchronise pas automatiquement les modifications des bords communs : reporter le terrain dans les deux cartes concernées.

Consulter le [dossier des cartes](../maps/README.md) et la [vue d’ensemble](STARTING_MAPS.svg).


## 14. Zones et héritage des niveaux

À la création, la fenêtre **Propriétés carte** s’ouvre aussi pour définir la zone et les niveaux. Une carte peut être la racine de sa propre zone ou être rattachée à une autre carte du catalogue.

| Champ | Rôle |
| --- | --- |
| Zone de rattachement | Identifiant de la carte racine ou d’un secteur rattaché ; son propre identifiant crée une zone indépendante |
| Niveau de zone | 1–100 ; utilisé sur la carte racine de la zone |
| Niveau local | Vide : héritage de la zone ; 1–100 : surcharge pour cette carte |

Priorité : **niveau du spawner > niveau local de la carte > niveau de la zone**. Les rattachements peuvent former une chaîne, mais les cycles et les références inexistantes sont refusés. Changer le niveau d’une zone met à jour les cartes et spawners qui en héritent au prochain chargement du serveur.

Certaines cartes déjà fournies conservent un niveau local explicite pour maintenir leur équilibrage. Vider ce champ permet de rétablir l’héritage. Définir le niveau de zone sur un secteur secondaire ne change pas la racine : modifier les propriétés de la carte racine.

Les données correspondantes sont `zone_id`, `zone_level` et `level`. Les coordonnées simples restent dans `spawns` ; les options individuelles sont dans `spawners`, avec `position`, `mob_id`, `level`, `count` et éventuellement `patrol`.

## 15. Outils de construction avancée

- **Recherche** : filtre par nom ou identifiant, sans tenir compte de la casse.
- **Zone** : filtre par zone racine, y compris ses secteurs rattachés.
- **Niv. min / max** : filtre par niveau effectif de la carte. Laisser vide pour ne pas limiter.
- **Pinceau 1, 3 ou 5** : peint un carré de cette taille à partir de la case cliquée ; fonctionne aussi avec Effacer. Les outils d’entités et de patrouille restent précis à une case.
- **Décor / Spawns / PNJ / Passages** : masquer ou afficher ces éléments dans le canevas, sans les supprimer ni changer les collisions.
- **Dupliquer** : crée une copie indépendante avec un nouvel identifiant. Les objets sont copiés et le rattachement de zone est conservé ; l’origine globale et le chevauchement sont retirés pour ne pas superposer involontairement deux scènes.
- **Supprimer carte** : autorisé pour une carte facultative qui n’a plus de passage entrant ni de secteur rattaché. Les cartes essentielles du tutoriel sont protégées.
- **Valider** : contrôle les cartes sans écrire de fichier, avec niveaux, espèces, groupes et patrouilles en plus des coordonnées et accès.
- **Synchroniser les raccords** : copie le terrain et le décor de la carte courante vers les bandes géométriques communes des voisins de la même zone. Les spawners, PNJ et passages restent propres à chaque carte. Cette opération est annulable ; valider ensuite pour vérifier qu’aucun objet du voisin n’a été recouvert.

Les murs et remparts ne sont pas destructibles pour le moment. Les spawners ne proposent pas encore de vagues programmées, de conditions de quête ou de tirage pondéré entre plusieurs espèces. Le repop utilise le délai global du moteur.


## Créer des secteurs qui se chevauchent

Sélectionnez la carte de départ, puis **Créer un secteur relié**. Choisissez un identifiant inédit, une direction (est, ouest, nord, sud) et le nombre de cases partagées (4 par défaut). Le nouveau secteur reprend les dimensions, l’ambiance et la zone du précédent. Le décor du raccord est copié, les coordonnées globales sont calculées et les passages aller-retour sont placés automatiquement aux bords. Les cases de passage et d’arrivée sont dégagées, ainsi qu’un chemin d’accès vers le passage existant. Un passage déjà placé sur cette même case est remplacé.

Peignez ensuite le reste du secteur, renommez-le avec **Propriétés carte**, puis enregistrez. **Synchroniser les raccords** reporte les modifications du décor partagé vers les secteurs voisins. Les PNJ et spawners restent propres à chaque carte. Pour des salles indépendantes comme une grotte, utilisez plutôt l’outil **Téléportation** : aucun chevauchement n’est nécessaire.

## Assembler les cartes comme des blocs

Cliquez sur **Assemblage des cartes**. Une fenêtre affiche toutes les cartes sous forme de blocs avec un aperçu du terrain, leur identifiant et leurs coordonnées globales en cases. Les cartes sans coordonnées sont rangées provisoirement sur une grille ; ce rangement n’est écrit que lorsque vous déplacez ou alignez un bloc.

- **Glisser un bloc** : déplacer sa position globale, avec un pas d’une case. Cela change son placement dans l’assemblage et ses futurs chevauchements, sans modifier ses téléportations existantes.
- **Molette** : zoomer ou dézoomer ; les barres de défilement permettent de parcourir l’ensemble.
- **Double clic** : retourner à l’éditeur de terrain sur cette carte.
- **Coller / espacer** : choisir une carte de référence, une direction et une distance. `0` colle les bords ; une valeur positive sépare les blocs ; une valeur négative les fait se chevaucher. Les deux blocs conservent leur zone respective.
- **Relier par un passage** : créer un passage sur la carte sélectionnée vers une autre carte, avec coordonnées du passage et de l’arrivée et retour automatique facultatif. Le placement visuel seul ne crée pas de connexion jouable. Les coordonnées sont locales à chaque carte.
- **Fusionner dans la sélection** : absorber une autre carte de la même zone dans le bloc sélectionné. La fusion est préparée et validée avant confirmation, puis peut être annulée avec **Annuler**. Le bloc absorbé disparaît du catalogue.

Une fusion conserve l’identifiant, le nom, l’ambiance et les propriétés de la carte sélectionnée. Les terrains sont réunis selon leurs coordonnées globales ; dans une partie commune, le terrain de la sélection a priorité. Un espace entre deux blocs devient du sol libre. Les apparitions, patrouilles, PNJ et passages externes sont décalés ; les téléportations entre les deux anciennes cartes sont supprimées. Les arrivées depuis les autres cartes sont recalculées. Les niveaux des spawners sont conservés explicitement.

La fusion est refusée si elle dépasse 128 × 128 cases, si les cartes n’ont pas la même taille de case ou la même zone, si deux spawners ou passages se superposent, si des PNJ ont le même identifiant, ou si la validation détecte un accès bloqué. Les sept cartes de référence du tutoriel peuvent recevoir une fusion mais ne peuvent pas être absorbées et supprimées. Aucun échec de fusion ne modifie les données.

Enregistrez depuis la fenêtre d’assemblage ou l’éditeur principal. Les positions et cartes fusionnées sont stockées dans les JSON. Redémarrez ensuite le serveur ; pour vérifier une fusion, utilisez une nouvelle session de jeu, car les sessions existantes peuvent encore référencer l’ancienne carte.

## Trajets rapides, rues et durée de voyage — alpha 0.11.0a8

**Trajets / rues** ouvre le plan des déplacements de la carte générale. La liste supérieure affiche les chemins avec leur distance, durée totale en jeu et durée réelle. Sélectionnez un chemin puis **Modifier le chemin**, ou ajoutez un nouveau chemin entre deux zones. Modifiez la distance en kilomètres ou la durée à pied en minutes de jeu. Si vous modifiez la durée, elle a priorité sur la distance ; la conversion utilise 6 km/h. Le ratio 1:3 s’applique au temps réel. Une téléportation de proximité entre cartes reste instantanée : ces réglages concernent les voyages sur les chemins rapides.

Dans la liste inférieure, choisissez la ville ou zone, puis ajoutez, renommez, supprimez ou réordonnez ses rues. Le champ **Bâtiments dans l’ordre** accepte les identifiants séparés par des virgules : la place est reliée à la rue, puis les bâtiments se suivent dans cet ordre. **Place centrale** change son identifiant. Ce plan règle les connexions sur la carte générale ; peignez séparément les chemins et bâtiments du terrain fixe avec les pinceaux. Les bâtiments sans interaction propre restent décoratifs dans le plan général.

Cliquez **Appliquer**, puis enregistrez les cartes et redémarrez le serveur. Les routes sont stockées sous `clearing.travel_routes`, et chaque plan local sous `village_streets` dans la carte correspondante. Les trois chemins rapides du tutoriel sont conservés ; leur distance, durée et nom peuvent être modifiés. Un plan contenant des identifiants dupliqués ou une distance invalide est refusé.

## Choisir les TP sur les cartes

**TP par clics** ouvre la carte de départ : choisissez une carte dans la liste et cliquez une case praticable. Nommez le passage et choisissez la destination. Cliquez ensuite sa case d’arrivée sur la carte de destination. Si le retour est activé, cliquez également la case de départ du retour puis sa case d’arrivée sur la carte d’origine. Les quatre cases sont donc choisies explicitement. Annuler une étape abandonne l’opération sans créer de passage partiel.

L’outil **Téléportation** propose aussi la case **Choisir les arrivées et le retour sur les cartes**. Désactivez-la pour garder la saisie des coordonnées et le retour voisin automatique des versions précédentes. Une destination vide crée une sortie complète vers la carte générale. Les cases d’arrivée ne doivent pas être des cases de TP, pour éviter de repartir aussitôt en boucle.

## Déplacer les objets et les patrouilles

Sélectionnez **Déplacer**, puis glissez un PNJ, un TP, un spawner, un décor ou un point de patrouille vers une autre case. Si plusieurs objets occupent la même case, choisissez celui à déplacer. Un clic de sélection suivi d’un clic sur la destination fonctionne aussi. Les points de patrouille sont les numéros orange affichés lorsque le calque Spawns est visible.

Déplacer un spawner décale également sa patrouille. Déplacer un point orange ne change que ce point. Déplacer un TP change sa case de départ ; sa destination et son arrivée restent celles que vous avez configurées. Déplacer un arbre, rocher, maison, mur ou rempart déplace également sa collision. Une opération vers une case bloquée, hors carte ou qui rend le catalogue invalide est refusée. Ctrl+Z annule le déplacement.

## Fusionner les grottes

Dans **Assemblage des cartes**, collez d’abord les salles pour obtenir le placement souhaité. Sélectionnez **cave_1**, puis absorbez **cave_2**, et enfin **cave_3** avec **Fusionner dans la sélection**. Les deux salles absorbées peuvent désormais disparaître du catalogue ; la première reste la carte de référence du tutoriel. Les passages externes et arrivées sont recalculés. La limite finale reste 128 × 128 cases. Utilisez une nouvelle session de jeu après fusion.

## Aperçu du rendu final et orientation des ponts — alpha 0.11.0a9

**Aperçu rendu final** ouvre dans le navigateur une page autonome avec le même rendu de terrain que le jeu : arbres, maisons, rochers, eau, ponts, murs et remparts. Aucun serveur de jeu n’est nécessaire. Les modifications non enregistrées sont incluses. Le sélecteur permet de consulter toutes les cartes de l’instantané ; la molette ou les boutons règlent le zoom, le glisser déplace la vue et **Vue entière** réinitialise le cadrage. Désactivez les repères pour voir seulement le décor.

L’aperçu est figé : après une modification dans le builder, cliquez à nouveau **Aperçu rendu final** pour générer une vue à jour. Il présente le terrain et les positions éditées, sans simuler les déplacements des PNJ, les combats ou le brouillard de découverte des joueurs.

Le réglage **Pont °** choisit l’orientation lors du placement avec le pinceau Pont : `0` ou `180` pour un pont orienté nord-sud, `90` ou `270` pour est-ouest. L’outil **Rotation pont** permet ensuite de cliquer un pont existant pour le tourner de 90°. Pour changer une traversée composée de plusieurs cases, tournez chacune des cases ou repeignez l’ensemble avec l’angle choisi. Les flèches ↕ / ↔ de l’éditeur indiquent le sens ; l’aperçu montre les planches et les rambardes.

Les orientations sont stockées dans `bridge_rotations` sous forme de `{ "position": [x,y], "rotation": 90 }`. Une case sans orientation explicite conserve l’ancien rendu à 0°. Les rotations restent conservées lors des duplications, synchronisations de raccords et fusions. Effacer ou remplacer une case de pont retire son orientation. La rotation est visuelle et ne modifie pas les collisions ni les chemins traversables. Enregistrez puis redémarrez le serveur pour appliquer le changement dans le jeu.
