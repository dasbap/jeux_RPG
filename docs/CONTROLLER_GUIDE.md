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

Le contrôleur est un outil externe au jeu. Il modifie les définitions, pas les sessions des joueurs en direct. La barre supérieure propose **Builder**, **Valider**, **Enregistrer le projet** et **Annuler modification**. Double-cliquer une ligne ouvre son formulaire. Les modifications restent en mémoire jusqu’à l’enregistrement.

| Onglet | Contrôles |
| --- | --- |
| Cartes / zones | Liste des cartes et rattachements ; ouvrir le builder, créer une carte, gérer les zones et raccords dans l’assemblage |
| Quêtes | Nom, description, PNJ donneur, élimination ou fabrication, cible, zone facultative, quantité et récompense XP |
| Mobs | Identifiant, nom, classe de base, rang, dégâts et tableau des matériaux donnés |
| Succès et titres | Nom, condition, seuil lorsqu’il est utilisé et titre obtenu |
| PNJ | Carte, nom, identifiant, dialogue, joueur lié facultatif et placement par clic |
| Monde | Délai de repop, XP des mobs, courbe d’XP, durée de séjour du marchand et vision des joueurs |

Les cartes fixes, les rencontres, les collisions, les rues et les durées des trajets se règlent depuis le **Builder**. Son guide complet se trouve dans [BUILDER_GUIDE.md](BUILDER_GUIDE.md).

## Builder intégré

Sélectionner une carte dans **Cartes / zones**, puis **Éditer la carte dans le builder**. Tous les outils existants sont disponibles, notamment **Assemblage des cartes**, **Aperçu rendu final** et **Trajets / rues**. Le builder utilise les espèces créées dans l’onglet Mobs même avant leur enregistrement.

Enregistrer depuis le builder valide et enregistre les trois catalogues du projet. En fermant le builder avec des modifications non enregistrées, choisir de les garder dans le contrôleur ou de les abandonner. Annuler depuis le contrôleur restaure aussi les modifications récupérées du builder.

Le bouton Supprimer d’une carte ouvre le builder : utiliser son outil **Supprimer carte**, qui protège les cartes du tutoriel et leurs références.

## Quêtes

Créer d’abord le PNJ donneur, puis ajouter la quête. Les objectifs disponibles sont :

- `kill` : vaincre une espèce, dans une zone donnée ou partout si la zone est vide.
- `craft` : fabriquer une recette de forge existante. Une amélioration ne compte pas comme une fabrication.

La quête est acceptée en parlant au PNJ, à proximité, hors menace ennemie, sur la carte de terrain. Le compteur démarre à l’acceptation. Les membres du groupe partagent la progression. Revenir parler au PNJ une fois l’objectif rempli accorde l’XP à chaque joueur, une seule fois. Le journal affiche les quêtes acceptées, leur avancement et leur état.

La quête `mira_hunt` contrôle le tutoriel : son nombre de gobelins, sa description et son XP sont modifiables. Son identifiant peut être renommé, par exemple en `mira_hunt_2` : son rôle de quête du tutoriel est conservé séparément. Son PNJ Mira et sa cible dans la lisière restent nécessaires au déroulement du tutoriel. Elle ne peut pas être supprimée. Les étapes du tutoriel et le verrouillage de la forge restent les mécanismes existants.

Les objectifs ne déclenchent pas de scripts libres, de nouvelles étapes de tutoriel ou des dialogues à branches. Les PNJ peuvent proposer plusieurs quêtes ; leur interaction accepte ou rend celles qui sont disponibles.

## Espèces et matériaux

Les classes de base disponibles sont Goblin, Orc et DragonWhelp. Une nouvelle espèce réutilise une de ces classes pour ses statistiques et compétences héritées ; elle peut avoir un nom, un rang, des dégâts et des matériaux différents. Le niveau et le nombre apparaissant ensemble se règlent par spawner dans le builder.

Dans le tableau du butin, ajouter/modifier une ligne ou la retirer, puis cliquer **Appliquer**. Les matériaux sont récupérés en dépeçant le corps. Les probabilités des matériaux rares et les recettes d’équipement conservent leurs règles actuelles ; cet écran édite les matériaux garantis.

Une espèce utilisée par un spawner ou une quête ne peut pas être supprimée. Le gobelin de référence est protégé. Renommer une espèce personnalisée met automatiquement à jour les spawners et les cibles de quêtes.

## Succès et titres

| Condition | Déclencheur / seuil |
| --- | --- |
| silent | Victoire sans alerte ennemie |
| untouched | Victoire sans dégâts au groupe ni aux invocations |
| fast | Victoire en au plus X secondes réelles |
| higher | Duel gagné contre un ennemi supérieur d’au moins X niveaux |
| superiority | Victoire avec plus de joueurs que d’ennemis au début |
| inferiority | Victoire avec moins de joueurs que d’ennemis au début |
| level | Niveau maximal atteint au moins X |
| kills | Au moins X créatures vaincues |

Le champ Seuil est masqué pour les conditions qui n’en utilisent pas. Les découvertes de zones gardent leurs succès automatiques. Les combats d’entraînement ne décernent pas de succès de victoire.

## PNJ

Créer/modifier un PNJ puis cliquer sa case sur la carte sélectionnée. La case doit être praticable et accessible. Le dialogue est du texte, sans exécution de code. Laisser le joueur lié vide pour un PNJ fixe ; `leader` ou un identifiant joueur lie le PNJ à ce joueur et utilise le suivi existant.

Supprimer un PNJ requis par une quête est refusé. Renommer son identifiant met automatiquement à jour les quêtes correspondantes.

## Monde et fichiers

La progression utilise `base × niveau^exposant`. Le repop s’applique après le délai d’absence de joueurs, en secondes de jeu. Le marchand séjourne le nombre d’heures configuré dans chaque village. La vision est en cases. Le ratio reste 1:3 et la marche à 6 km/h.

L’enregistrement valide les références avant d’écrire `world.json`, `mobs.json` et `content.json`. Chaque fichier est remplacé atomiquement ; une erreur d’écriture détectée restaure les fichiers déjà remplacés. Cela ne constitue pas une transaction garantie face à une coupure du processus ou du système pendant les remplacements.

Pour utiliser un projet séparé dans le jeu :

```powershell
$env:RPG_MAPS_FILE = 'D:\RPG\mon_monde\maps'
python main.py
```

Le jeu lit `content.json` et `mobs.json` dans ce dossier. On peut sélectionner le contenu séparément avec `RPG_CONTENT_FILE`. Redémarrer le serveur après l’enregistrement. Tester les changements d’objectifs, de titres ou de cartes fusionnées avec de nouvelles sessions ; les anciennes sessions conservent leur progression.

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
