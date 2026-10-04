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

La quête `mira_hunt` contrôle le tutoriel : son nombre de gobelins, sa description et son XP sont modifiables. Son identifiant, son PNJ Mira et sa cible dans la lisière sont nécessaires au déroulement du tutoriel. Elle ne peut pas être supprimée. Les étapes du tutoriel et le verrouillage de la forge restent les mécanismes existants.

Les objectifs ne déclenchent pas de scripts libres, de nouvelles étapes de tutoriel ou des dialogues à branches. Les PNJ peuvent proposer plusieurs quêtes ; leur interaction accepte ou rend celles qui sont disponibles.

## Espèces et matériaux

Les classes de base disponibles sont Goblin, Orc et DragonWhelp. Une nouvelle espèce réutilise une de ces classes pour ses statistiques et compétences héritées ; elle peut avoir un nom, un rang, des dégâts et des matériaux différents. Le niveau et le nombre apparaissant ensemble se règlent par spawner dans le builder.

Dans le tableau du butin, ajouter/modifier une ligne ou la retirer, puis cliquer **Appliquer**. Les matériaux sont récupérés en dépeçant le corps. Les probabilités des matériaux rares et les recettes d’équipement conservent leurs règles actuelles ; cet écran édite les matériaux garantis.

Une espèce utilisée par un spawner ou une quête ne peut pas être supprimée. Le gobelin de référence est protégé. L’identifiant d’une espèce existante est conservé afin de préserver ses références.

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

Supprimer un PNJ requis par une quête est refusé. Modifier son identifiant nécessite de mettre à jour les quêtes correspondantes avant l’enregistrement ; conserver son identifiant est préférable.

## Monde et fichiers

La progression utilise `base × niveau^exposant`. Le repop s’applique après le délai d’absence de joueurs, en secondes de jeu. Le marchand séjourne le nombre d’heures configuré dans chaque village. La vision est en cases. Le ratio reste 1:3 et la marche à 6 km/h.

L’enregistrement valide les références avant d’écrire `world.json`, `mobs.json` et `content.json`. Chaque fichier est remplacé atomiquement ; une erreur d’écriture détectée restaure les fichiers déjà remplacés. Cela ne constitue pas une transaction garantie face à une coupure du processus ou du système pendant les remplacements.

Pour utiliser un projet séparé dans le jeu :

```powershell
$env:RPG_MAPS_FILE = 'D:\RPG\mon_monde\maps'
python main.py
```

Le jeu lit `content.json` et `mobs.json` dans ce dossier. On peut sélectionner le contenu séparément avec `RPG_CONTENT_FILE`. Redémarrer le serveur après l’enregistrement. Tester les changements d’objectifs, de titres ou de cartes fusionnées avec de nouvelles sessions ; les anciennes sessions conservent leur progression.
