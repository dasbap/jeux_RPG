# Les Cloches sous les racines — intégration

Le projet Builder `projects/authored` contient le récit jouable. Son export vers `jeuxRPG/maps` est validé avant la construction du client Windows. Les textes et les lieux ne sont pas définis dans le moteur Python.

## Contenu livré

- 26 quêtes facultatives : les 14 quêtes existantes sont réécrites et 12 nouvelles quêtes relient Rosée, la carrière, Brume et le Sanctuaire.
- 8 personnages : Maël, Mira, Garrik, Sève, Néran, Rusk, Oriel et Élyne.
- 7 lieux à examiner : la borne, l’ancien chargement, l’inscription de la carrière, trois stèles et le poste de garde des Ruines.
- 18 notes et témoignages conservés dans le journal.
- Deux conclusions personnelles, avec les mêmes récompenses : rétablir l’ancien accord ou partager autrement la Veille.
- Deux titres de récit : Porte-mémoire et Témoin de la Veille.
- Une réplique du Seigneur gobelin au début de son engagement, affichée sans interrompre le combat.

Parler à un personnage n’accepte aucun contrat. Le dialogue présente les sujets, les objectifs, le niveau conseillé, la récompense et les prérequis avant de proposer **Accepter cette quête**. Une quête prête se rend explicitement au donneur. Les contrats répétables doivent être acceptés à nouveau après chaque remise.

Les quêtes et les choix sont propres à chaque personnage. Un combat partagé peut faire progresser les quêtes déjà acceptées par les participants présents. La fabrication compte pour son propriétaire. Une remise donne son XP à ce personnage ; elle n’accepte pas les quêtes d’un allié et ne choisit pas sa conclusion.

L’exploration et les sorties restent libres. Les sorties du village et des forêts ouvrent la carte globale. L’arrivée à Brume ouvre une nouvelle partie du récit. Seule l’utilisation de la forge de Rosée demande toujours la remise de **Protéger la lisière** : quatre gobelins ordinaires, puis retour à Mira. Les gardes et le chef ne comptent pas dans ce contrat.

La fabrication précède chaque quête d’amélioration. Les pièces déjà possédées ou améliorées sont reconnues ; un objet déjà validé ne cesse pas de l’être si le joueur le remplace ensuite. Les bonus de panoplie 2/4/5 ne changent pas.

Les indices peuvent être lus avant d’accepter leur quête. Les anciennes victoires enregistrées sur le Seigneur gobelin sont reconnues. L’hommage aux Veilleurs ne demande pas de refaire la chasse. Rusk remplace le déserteur hostile : les anciennes instances de ce dernier sont retirées des champs sauvegardés et des arrivées en attente.

Trois lucioles, trois sangliers ronciers et trois Veilleurs sont placés dans leurs zones respectives, afin que leurs contrats courts ne nécessitent pas d’attendre une réapparition.

## Modifier dans le Builder

Le catalogue **Histoire / dialogues / indices** du contrôleur distingue l’accueil de chaque personnage, ses sujets de conversation, les réponses proposées et les notes du journal. Les textes longs utilisent des champs multilignes. Les listes de conditions et d’indices sont des listes JSON, par exemple `["noms_mousse"]`.

L’aperçu montre la définition complète d’un élément. La validation refuse une référence inconnue, un lieu d’indice absent et une boucle entre objectifs, quêtes et dialogues qui rendrait une suite impossible.

Les quêtes utilisent le catalogue **Quêtes**. Le type `story` valide une liste d’indices ou de témoignages ; son compteur correspond au nombre de ces objectifs. Les niveaux conseillés ne verrouillent pas l’accès. Les prérequis restent éditables dans le formulaire existant.

Les objets à examiner sont des lieux de carte avec `interaction: "inspect"` ; les personnages utilisent `talk`. La réplique ennemie se règle dans le spawner avec `battlecry`. Déplacer les objets, les PNJ ou les ennemis reste une opération du Builder.

Renommer une quête met à jour les conditions des conversations et conserve son ancien identifiant pour les sauvegardes. Renommer un PNJ ou une carte met à jour les références d’indices correspondantes. Supprimer un élément encore nécessaire à une quête est refusé lors de la validation.

## Sauvegardes et vérifications

Les anciennes quêtes partagées sont reprises une seule fois dans l’état personnel, sans redistribuer leur XP. Les quêtes rendues et l’accès à la forge restent reconnus. Les notes, les réponses et la conclusion sont conservées après redémarrage. Les réponses envoyées au client ne contiennent pas les choix privés des autres joueurs.

```powershell
.venv-reprise/Scripts/python.exe -m pytest test/test_narrative.py -q
.venv-reprise/Scripts/python.exe scripts/verify_optional_content.py --ui-fixtures .data/quest-ux/fixtures.json
node scripts/verify_quest_ui.cjs .data/quest-ux/fixtures.json
node scripts/verify_narrative.cjs --packaged
```

Le test Electron utilise une sauvegarde jetable, bloque le réseau et traverse de vraies conversations, l’acceptation et la remise d’une quête, un indice, le déblocage et la fabrication à la forge, puis le redémarrage de l’application. Il contrôle aussi le dialogue sur un écran de 390 pixels de large.
