# Contrôleur du projet RPG

## Démarrer

Depuis le dépôt :

```powershell
python -m pip install --upgrade .
python controller.py
```

Après installation, le raccourci fonctionne aussi :

```powershell
jeux-rpg-controller
```

Le contrôleur utilise le dossier `maps` du répertoire courant. Pour un projet séparé :

```powershell
python controller.py D:\RPG\mon_monde\maps
```

Un dossier neuf est initialisé avec les catalogues fournis. Tkinter doit être présent dans Python ; il est normalement inclus avec l’installation Windows.

## Organisation

Le contrôleur est un outil externe au jeu. Il modifie les définitions, pas les sessions des joueurs en direct. La barre supérieure propose **Builder**, **Valider**, **Enregistrer le projet**, **Annuler modification** et **Rétablir**. Double-cliquer une ligne ouvre son formulaire. Les modifications restent en mémoire jusqu’à l’enregistrement.

| Onglet | Contrôles |
| --- | --- |
| Cartes / zones | Liste des cartes et rattachements ; ouvrir le builder, créer une carte, gérer les zones et raccords dans l’assemblage |
| Quêtes | Nom, description, PNJ donneur, élimination ou fabrication, cible, zone/carte facultatives, quantité et récompense XP |
| Mobs | Identifiant, nom, classe de base, rang, dégâts et tableau des matériaux donnés |
| Succès et titres | Condition, cible facultative, zone et carte facultatives, seuil et titre |
| Classes / modèles | Classes jouables, modèles de créatures et invocations : stats, énergies, paliers, affinités et profil de combat |
| Compétences simples | Dégâts, soin et stun réutilisables |
| Compétences moteur | Effets multiples, invocations, buffs, coûts, scaling, portée et incantation |
| PNJ | Carte, nom, identifiant, dialogue, joueur lié facultatif et placement par clic |
| Monde | Délai de repop, XP des mobs, courbe d’XP, durée de séjour du marchand et vision des joueurs |

Les cartes fixes, les rencontres, les collisions, les rues et les durées des trajets se règlent depuis le **Builder**. Son guide complet se trouve dans [BUILDER_GUIDE.md](BUILDER_GUIDE.md).

## Builder intégré

Sélectionner une carte dans **Cartes / zones**, puis **Éditer la carte dans le builder**. Tous les outils existants sont disponibles, notamment **Assemblage des cartes**, **Aperçu rendu final** et **Trajets / rues**. Le builder utilise les espèces créées dans l’onglet Mobs même avant leur enregistrement.

Enregistrer depuis le builder valide et enregistre les quatre catalogues du projet. En fermant le builder avec des modifications non enregistrées, choisir de les garder dans le contrôleur ou de les abandonner. Annuler depuis le contrôleur restaure aussi les modifications récupérées du builder.

Le bouton Supprimer d’une carte ouvre le builder : utiliser son outil **Supprimer carte**, qui protège les cartes du tutoriel et leurs références.

## Quêtes

Créer d’abord le PNJ donneur, puis ajouter la quête. Les objectifs disponibles sont :

- `kill` : vaincre une espèce, dans une zone donnée ou partout si la zone est vide. Le champ Carte restreint à un secteur précis. Les anciens objectifs utilisant un ID de secteur dans Zone restent reconnus.
- `craft` : fabriquer une recette de forge existante. Une amélioration ne compte pas comme une fabrication.

La quête est acceptée en parlant au PNJ, à proximité, hors menace ennemie, sur la carte de terrain. Le compteur démarre à l’acceptation. Les membres du groupe partagent la progression. Revenir parler au PNJ une fois l’objectif rempli accorde l’XP à chaque joueur, une seule fois. Le journal affiche les quêtes acceptées, leur avancement et leur état.

La quête `mira_hunt` contrôle le tutoriel : son nombre de gobelins, sa description et son XP sont modifiables. Son identifiant peut être renommé, par exemple en `mira_hunt_2` : son rôle de quête du tutoriel est conservé séparément. Son PNJ Mira et sa cible dans la lisière restent nécessaires au déroulement du tutoriel. Elle ne peut pas être supprimée. Les étapes du tutoriel et le verrouillage de la forge restent les mécanismes existants.

Les objectifs ne déclenchent pas de scripts libres, de nouvelles étapes de tutoriel ou des dialogues à branches. Les PNJ peuvent proposer plusieurs quêtes ; leur interaction accepte ou rend celles qui sont disponibles.

## Espèces et matériaux

Les modèles de base proviennent de **Classes / modèles**. Une espèce peut utiliser tout modèle non invocation, y compris un modèle personnalisé. Les caractéristiques héritées peuvent être remplacées par des formules de base et de croissance. Une espèce dispose de son nom, rang, dégâts, multiplicateur XP, matériaux et capacités. Le niveau et le nombre apparaissant ensemble se règlent par spawner dans le builder.

Dans **Drops**, configurer pour chaque matériau la probabilité, les tirages indépendants, la quantité minimale/maximale et la rareté. Les décimales acceptent un point ou une virgule. Les matériaux sont récupérés en dépeçant le corps. **Aperçu / références** calcule la probabilité d’au moins un drop, la quantité moyenne et l’XP selon les deux niveaux sélectionnés.

Une espèce utilisée par un spawner ou une quête ne peut pas être supprimée. Le gobelin de référence est protégé. Renommer une espèce personnalisée met automatiquement à jour les spawners et les cibles de quêtes.

## Succès et titres

Les succès appartiennent à l’aventure du groupe. Les filtres vides signifient toutes les cibles et tous les lieux. Les filtres renseignés se combinent avec **ET** : une créature d’une autre espèce ou tuée ailleurs ne compte pas. La cible désigne une espèce exacte ; une sous-espèce peut être sélectionnée séparément. La zone inclut ses cartes rattachées ; la carte désigne un secteur précis. Le contrôleur refuse une carte qui n’appartient pas à la zone choisie.

Exemple : **Ajouter** → identifiant `gobelins_666` → condition `kills` → seuil `666` → cible `goblin` → zone `lisiere` → carte `hunt` (facultative) → titre `Fléau du campement`. Sans cible, toutes les créatures du lieu comptent. Sans lieu, tous les gobelins de l’aventure comptent.

| Condition | Seuil | Cible / lieu |
| --- | --- | --- |
| `kills` | Nombre de créatures éliminées | Espèce facultative, zone et/ou carte |
| `silent` | Nombre de victoires sans alerte | Espèce présente parmi les victimes, zone et/ou carte |
| `untouched` | Nombre de victoires sans dégâts au groupe ni aux invocations | Mêmes filtres |
| `victories` | Nombre de victoires complètes | Mêmes filtres |
| `superiority` / `inferiority` | Nombre de victoires avec avantage / désavantage numérique initial | Mêmes filtres |
| `fast` | Temps maximal d’une victoire en secondes réelles, décimales autorisées | Mêmes filtres |
| `higher` | Différence minimale de niveaux pour un duel gagné | Mêmes filtres |
| `level` | Niveau maximal atteint, 1–100 | Aucun filtre |
| `craft` | Nombre de fabrications, hors améliorations | Recette facultative, zone et/ou carte |
| `quests` | Nombre de quêtes distinctes terminées | Quête facultative, lieu où elle a été rendue |
| `discover` | Nombre de zones distinctes découvertes | Sans filtre pour plusieurs zones ; zone ou carte précise avec seuil 1 |

Une victoire exige la fin réelle du combat, sans ennemis ni arrivées en attente. Les conditions sans alerte et sans dégâts portent sur tout le combat, même si une cible est précisée. Les entraînements ne comptent pas. Les découvertes automatiques de zones restent disponibles.

Les succès acquis sont conservés par identifiant ; modifier le titre ne retire pas l’accomplissement. Deux succès peuvent partager un titre sans se débloquer mutuellement. Renommer conserve l’ancien identifiant. Pour remplacer un objectif acquis par un objectif différent, créer un nouveau succès plutôt que réutiliser son identifiant.

Les anciens totaux de kills restent disponibles. Les anciennes sessions ne contiennent pas l’espèce et le lieu des kills historiques : les nouveaux compteurs filtrés démarrent avec cette mise à jour. Les quêtes déjà terminées restent reconnues sans filtre de lieu ; leur lieu historique n’est pas inventé.

Les cibles inconnues et suppressions laissant une référence sont refusées avant écriture. Renommer un mob, une quête ou une carte met à jour les succès concernés et conserve les compteurs déjà enregistrés sous ses anciens identifiants. Un objectif portant sur une seule quête ou un seul lieu de découverte utilise un seuil de 1.

## PNJ

Créer/modifier un PNJ puis cliquer sa case sur la carte sélectionnée. La case doit être praticable et accessible. Le dialogue est du texte, sans exécution de code. Laisser le joueur lié vide pour un PNJ fixe ; `leader` ou un identifiant joueur lie le PNJ à ce joueur et utilise le suivi existant.

Supprimer un PNJ requis par une quête est refusé. Renommer son identifiant met automatiquement à jour les quêtes correspondantes.

## Monde et fichiers

La progression utilise `base × niveau^exposant`. Le repop s’applique après le délai d’absence de joueurs, en secondes de jeu. Le marchand séjourne le nombre d’heures configuré dans chaque village. La vision est en cases. Le ratio reste 1:3 et la marche à 6 km/h.

L’enregistrement valide les références avant d’écrire `world.json`, `mobs.json`, `content.json` et `classes.json`. Chaque fichier est remplacé atomiquement ; une erreur d’écriture détectée restaure les fichiers déjà remplacés. Cela ne constitue pas une transaction garantie face à une coupure du processus ou du système pendant les remplacements.

Pour utiliser un projet séparé dans le jeu :

```powershell
$env:RPG_MAPS_FILE = 'D:\RPG\mon_monde\maps'
python main.py
```

Le jeu lit `content.json`, `mobs.json` et `classes.json` dans ce dossier. On peut sélectionner le contenu séparément avec `RPG_CONTENT_FILE`. Redémarrer le serveur après l’enregistrement. Tester les changements d’objectifs, de titres ou de cartes fusionnées avec de nouvelles sessions ; les anciennes sessions conservent leur progression.

## Renommer les identifiants — alpha 0.11.0a13

Sélectionner une ligne puis **Renommer identifiant**, ou modifier directement le champ **Identifiant** dans le formulaire des quêtes, succès, mobs et PNJ. Les IDs acceptent 1 à 64 lettres minuscules, chiffres et underscores : `mira_hunt_2` est valide. Le nom affiché est du texte libre et accepte aussi ce nom. Les doublons sont refusés.

Les références aux espèces, PNJ et cartes personnalisées sont mises à jour. Pour une quête renommée, les anciens identifiants sont conservés dans `previous_ids` : après redémarrage du serveur, les quêtes déjà acceptées ou terminées retrouvent leur progression, sans seconde récompense. Un ancien identifiant ne peut pas être réutilisé pour une autre quête.

La quête initiale de Mira peut être renommée. Les IDs `goblin`, `mira`, `forge` et les sept cartes obligatoires restent des références internes protégées ; créer une définition personnalisée pour un autre ID. Enregistrer le projet puis redémarrer le serveur. Tester les renommages de cartes ou de mobs dans une nouvelle session : les scènes déjà chargées conservent leurs anciennes références.


## Espèces, sous-espèces et butin

Dans l’onglet Mobs, sélectionnez une espèce puis **Modifier**, ou utilisez **Ajouter** pour créer une espèce. **Créer une sous-espèce** part de l’espèce sélectionnée. Les identifiants tels que `goblin_mage_2` sont acceptés. Une sous-espèce hérite des champs absents de son parent ; les listes de drops et capacités explicitement définies remplacent celles du parent. Les cycles de parenté sont refusés. L’éditeur enregistre les valeurs affichées comme des valeurs explicites : elles deviennent indépendantes des changements ultérieurs du parent.

Les classes Goblin, Orc et DragonWhelp sont des modèles de personnage sûrs ; les espèces peuvent avoir un nom, un rang et des propriétés propres. Les statistiques suivent `base + croissance × (niveau − 1)`. Les dégâts de l’attaque classique ont également une base et une croissance par niveau. Le niveau effectif provient du spawner ou, à défaut, de la zone.

Les capacités configurables sont les dégâts, le soin personnel et l’étourdissement. Pour chacune : nom, niveau de déblocage, puissance et croissance, portée, durée d’incantation, délai de récupération, concentration et durée de l’étourdissement. Une incantation avec concentration est interrompue par les dégâts ; les capacités offensives exigent portée et visibilité. Les durées sont exprimées en secondes de jeu ; l’étourdissement est arrondi au prochain tick d’effet. Aucun code Python arbitraire n’est exécuté depuis le catalogue.

Chaque ligne de drop définit un identifiant d’objet, une probabilité entre 0 et 1, un nombre de tirages indépendants, une quantité minimale et maximale par réussite, et une indication de rareté. Exemple : probabilité 0,1, trois tirages, quantité 1–2 : jusqu’à trois réussites pour un total de six objets. La rareté sert au classement du bestiaire ; elle ne modifie pas la probabilité. Les règles explicites remplacent les anciens drops communs et rares. Un objet doit correspondre aux identifiants de matériaux utilisés par les recettes pour être utilisable à la forge.

## Expérience des ennemis

La récompense est arrondie à l’entier :

`XP = XP de base du monde × niveau du mob × facteur de classe XP × multiplicateur de l’espèce × 4^(écart / 10)`

L’écart est `niveau du mob − niveau du tueur`, plafonné entre −10 et +10. Le facteur de niveau vaut donc ×4 dès +10 et ÷4 dès −10. Les classes XP configurables sont normal (1), guerrier (1,5), lanceur de sorts (1,8), élite (2,5) et boss (4). Les anciennes espèces sans classe XP explicite conservent les facteurs de modèle Goblin (1), Orc (1,6) et DragonWhelp (2,5).

Le dernier coup identifie le tueur ; une invocation est attribuée à son propriétaire, un saignement à sa source. La récompense calculée est accordée à chaque membre du groupe, comme auparavant. Un multiplicateur nul supprime l’XP. L’entraînement ne donne ni XP ni butin. Sauvegardez les catalogues et redémarrez le serveur pour appliquer les modifications.


## Conditions d’acceptation des quêtes

Lors de l’ajout ou de la modification d’une quête, la fenêtre **Prérequis de quête** permet de définir :

- Le niveau minimum, de 1 à 100 ; chaque joueur du groupe doit l’atteindre.
- Les succès requis, sélectionnables par leur nom et identifiant.
- Les quêtes qui doivent être terminées, sélectionnables par leur nom et identifiant.

Les listes permettent plusieurs sélections par clic. Toutes les conditions sélectionnées sont obligatoires ; une liste vide n’impose aucune condition de ce type. Les succès et quêtes utilisent la progression partagée du groupe. Le PNJ explique les conditions manquantes et le serveur refuse l’acceptation tant qu’elles ne sont pas remplies. Les quêtes déjà acceptées restent actives même si les prérequis sont modifiés.

Le catalogue utilise par exemple `"requirements": {"level": 5, "achievements": ["kills_10"], "quests": ["mira_hunt"]}`. Les références inconnues, les doublons et les dépendances circulaires sont refusés à la sauvegarde. Renommer une quête ou un succès met à jour ses références dans les prérequis. L’absence de `requirements` conserve l’accès sans condition des anciens catalogues. Sauvegardez puis redémarrez le serveur.


Les probabilités de drop acceptent un point ou une virgule : `0.8` et `0,8` valent 80 %, même lorsque la valeur précédente était `1` ou `0`. Les nombres de tirages et les quantités d’objets restent entiers.


## Bibliothèque de compétences et classes humaines

L’onglet **Compétences** permet de créer et modifier des capacités réutilisables de dégâts, soin personnel ou étourdissement. Les capacités créées sur un mob et les compétences humaines et monstres intégrées au jeu sont également proposées dans les listes de sélection. Les références portent les préfixes `skill:`, `mob:` ou `native:` ; elles incluent le nom de leur source et de la compétence.

Dans **Mobs → Modifier → Capacités**, utilisez **Réutiliser une compétence**, sélectionnez la source puis définissez le niveau de déblocage et la portée. Les attaques humaines natives conservent leurs effets et leur coût d’énergie ; le mob reçoit l’énergie requise et la régénère. Les invocations et résurrections natives sont actuellement proposées aux classes humaines uniquement : l’IA des mobs ne gère pas ces cibles et propriétaires spécifiques. Les capacités directement créées dans le contrôleur restent disponibles comme auparavant.

Dans **Classes / modèles**, **Ajouter** copie une définition existante. Cette copie devient une classe indépendante : elle ne dépend plus d’une sous-classe Python ou d’un modèle imposé à l’exécution.

1. Définissez l’identifiant, le nom, le type et les statistiques initiales.
2. Réglez les énergies, leur capacité et leur régénération.
3. Configurez les paliers de croissance. Chaque palier ajoute ses gains à chaque niveau à partir de son seuil ; un déblocage d’énergie ne se produit qu’une fois.
4. Choisissez les compétences existantes, leurs niveaux de déblocage, portée et coût. `−1` conserve automatiquement la valeur de la compétence ; `0` est une valeur explicite.
5. Réglez le profil d’attaque : statistique utilisée, base, coefficient, minimum et portée. Le profil invocateur conserve le comportement de protection et d’attaque des invocations.

Une énergie requise par une compétence et absente de la progression est ajoutée par l’éditeur. Les invocations natives restent utilisables avec le moteur existant. Les anciennes classes personnalisées sont converties lors de l’ouverture du projet ; **Sauvegarder** écrit leur définition universelle. Les anciennes formules de croissance sont conservées pour éviter de changer leurs résultats.

**Portée 0 signifie soi-même uniquement** : aucune autre entité ne peut être ciblée, même sur la même case. Cela convient aux soins, protections et invocations personnelles. Une attaque offensive de portée 0 n’a pas de cible valide, car le moteur interdit de s’attaquer soi-même. Les contrôles s’appliquent dans le client et le serveur.

Après sauvegarde et redémarrage du serveur, les classes jouables apparaissent dans la sélection de personnage du navigateur. Les définitions universelles, compétences intégrées et progressions sont stockées dans `maps/classes.json`. Les quêtes, PNJ et compétences partagées du contrôleur restent dans `maps/content.json`. Le renommage d’une classe conserve ses anciens identifiants et met à jour les références aux mobs et invocations. Ne supprimez pas une classe utilisée par des sauvegardes.

Les anciens imports Python (`Knight`, `Mage`, etc.) restent des alias de compatibilité ; ils ne contiennent plus de statistiques, compétences ou progression spécifiques. Le moteur générique construit les personnages depuis le catalogue. Le format détaillé est décrit dans [CLASS_FORMAT.md](CLASS_FORMAT.md).

## Rechercher, dupliquer, vérifier

Chaque onglet propose une recherche par mots sur identifiant, nom et détails, insensible à la casse. Tous les mots doivent correspondre. Le tableau conserve la sélection lorsque la ligne reste visible. Les barres de défilement facilitent les grands catalogues.

**Dupliquer** crée une définition indépendante dans Quêtes, Succès, Mobs, Classes et Compétences. Les alias historiques et le rôle du tutoriel ne sont pas copiés. Les cartes se copient dans le builder ; les PNJ se placent depuis leur éditeur. **Annuler modification** et **Rétablir** gèrent jusqu’à 30 états ; une nouvelle modification supprime la branche de rétablissement.

**Aperçu / références** affiche la définition et les chemins des éléments qui l’utilisent. Pour une classe, sélectionner le niveau pour voir stats, énergies, attaque et compétences. Pour un mob, sélectionner son niveau et celui du joueur pour vérifier stats héritées/remplacées, dégâts, XP et probabilités de drop. Le premier gobelin du tutoriel conserve son réglage de PV particulier ; l’aperçu gobelin utilise les PV habituels de chasse.

**Valider** présente un diagnostic par module : contenu/classes, espèces/drops, compétences, cartes/placements et références des succès. Il peut afficher plusieurs erreurs de catégories différentes et des avertissements non bloquants, par exemple un drop à 0 %. Le diagnostic ne modifie pas les catalogues. L’enregistrement applique également la validation.

## Modifier une compétence moteur

L’onglet **Compétences moteur** édite les définitions de `classes.json`. **Ajouter** copie une compétence et demande une référence `ability:mon_identifiant`. **Dupliquer** crée également une copie indépendante. Les compétences simples restent dans leur onglet dédié.

Les propriétés règlent type, énergie, coût de base, cooldown, ciblage, type de dégâts et portée. Portée `−1` conserve le calcul automatique ; `0` impose une cible personnelle. Le formulaire d’incantation règle `seconds` et `concentration`. Le formulaire de balance règle le coût fixe (`−1` = absent), les coefficients de coût/effets/stats et le saignement.

Chaque effet possède une clé unique (`damage`, `heal`, etc.), une valeur (`−1` = aucune valeur), une durée en unités du moteur, une statistique visée, une altération et éventuellement un modèle/palier d’invocation. Les types et paliers inconnus sont refusés. Utiliser une compétence existante comme point de départ préserve les effets attendus par son type. Les handlers restent limités aux gestionnaires sûrs du moteur ; aucun script libre n’est exécuté.

Les modèles d’invocations conservent des paliers tels que `BL`, les classes humaines des niveaux numériques. Les affinités acceptent les types `PHYSICAL`, `MAGIC`, `SACRED`, séparés par des virgules. Au moins une classe doit rester jouable. Redémarrer le serveur après enregistrement.

Une modification d’une compétence moteur est partagée par toutes ses références. Les capacités de mobs reçoivent la définition du projet, y compris une compétence nouvellement créée. L’IA des mobs ne gère toujours pas les invocations et résurrections : ces compétences sont réservées aux modèles liés à un joueur.

Les limites et le périmètre contrôlés sont détaillés dans [CONTROLLER_AUDIT.md](CONTROLLER_AUDIT.md).
