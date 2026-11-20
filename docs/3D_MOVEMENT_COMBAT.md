# Rendu 3D, déplacement libre et animations de combat

Le client affiche les cartes physiques dans une scène **WebGL en 3D**, avec un
style original coloré : personnages aux grandes têtes, armes séparées, végétation,
maisons à toits inclinés, remparts et rochers en volume. Les modèles sont générés
localement ; aucun modèle, texture ou sprite de Guardian Tales n'est utilisé.

La caméra garde une **orientation fixe**, sans rotation à la souris ou au tactile.
Elle suit le personnage. Le zoom et l'inspection par la minicarte conservent cet
angle. La carte stratégique et les menus restent en 2D.

Les personnages tournent entièrement dans leur direction de déplacement ; leurs
armes et boucliers gardent le même côté du corps. Les gardes interpolent chaque
pas entre les positions réellement reçues, avec une seconde de tampon visuel
pour absorber les intervalles irréguliers sans prédire leur trajectoire. L'animation
de marche et l'orientation suivent ce déplacement affiché. Les groupes abstraits de la simulation du monde ne
sont plus dessinés comme des PNJ sans interaction dans la scène locale ; les
monstres de combat et les membres individuels des patrouilles restent visibles.

## Commandes

Les touches d’action et de menus sont personnalisables dans Options.
Voir [la liste des raccourcis](KEYBINDINGS.md).

- **ZQSD, WASD ou flèches** : déplacement libre ; relâcher arrête le mouvement.
- **Joystick tactile** : direction analogique, limitée et vérifiée par le moteur.
- **Clic sur le sol** : trajet proposé par le navigateur, parcouru en continu.
- **Clic sur un personnage** : sélection ; clic sur un PNJ : approche et interaction.
- **Espace** ou bouton d'attaque existant : attaque d'une cible à portée.
- Le cercle autour du personnage représente la portée de son attaque simple.

La carte utilise toujours des cellules pour stocker le terrain et calculer les
chemins. Les positions des joueurs sont désormais continues : le mouvement ne
téléporte plus le joueur d'une cellule à la suivante. La grille reste interne
pour l'IA et les anciens clients ; les modèles affichés sont interpolés.

## Autorité du moteur

Le contrôle libre est calculé localement, image par image, sans freinage
selon l'écart serveur et sans retour automatique vers les anciennes positions.
Le client envoie sa position avec `move_axis` ou `stop_move`. Le moteur accepte
exactement une position valide, sans simuler un second mouvement concurrent.

Le moteur vérifie la distance avec sa propre horloge. Le crédit inutilisé
est plafonné à une seconde réelle de mouvement pour absorber les irrégularités
réseau. Le temps de marche couvert par un paquet tardif reste compté
intégralement. Le spam et les arrêts répétés ne rechargent pas ce crédit.
Le budget respecte les ralentissements d'attaque, d'incantation et de furtivité.
Les obstacles, la mort et les étourdissements restent des contraintes du jeu.
Un dépassement est refusé par le moteur. Un paquet refusé faute de crédit est
retransmis après un court délai, sans reculer le modèle local ni accélérer sa
marche. La dernière position validée continue de faire autorité pour le combat.
Les états ordinaires n'interfèrent pas avec la position locale, même au repos.

Les commandes sans position et les chemins `walk` gardent leur simulation
moteur. Un changement de carte initialise la position d'arrivée avant le premier
envoi ; une touche ou un joystick maintenu reprend dans la nouvelle zone. Les
réponses d'une ancienne zone sont ignorées, même après un retour dans celle-ci.
Les attaques
et incantations autorisent la marche à **55 % de la vitesse habituelle**.
La portée et les effets du combat restent décidés par le moteur.

La sélection d'une cible utilise la position locale affichée. Les attaques et
compétences emportent aussi cette position : le moteur vérifie la vitesse et le
terrain avant de vérifier la portée. Les rapports de mouvement et les positions
d'attaque partagent une séquence ; un ancien paquet ou sa retransmission ne peut
pas rétablir une position plus proche après un recul. Les rapports sont envoyés
au plus toutes les 80 ms pendant la marche, sous réserve du temps réseau.

À la fin de la préparation d'un coup ou d'une compétence de monstre, le moteur
attend brièvement un rapport couvrant cette fin si sa cible utilise le mouvement
local. Il revérifie ensuite portée et visibilité. L'attente est bornée par
l'expiration de l'entrée de mouvement, pour ne pas protéger indéfiniment un client
déconnecté. Les anciens clients et les trajets pilotés par le moteur restent pris
en charge.

Les états périmés sont filtrés ; les révisions des accusés de réception
sont suivies séparément de celles des états complets.

## Animations

Le moteur publie des événements visuels après ses décisions :

- Attaque de mêlée : mouvement du bras et de l'arme, arc lumineux du coup.
- Tir : projectile et traînée ; magie offensive : orbe et impact.
- Incantation : aura et particules pendant la préparation du sort.
- Soin ou résurrection : croix et lumière montantes.
- Renforcement : anneau et flèches ascendantes ; affaiblissement : particules
  violettes autour de la cible.
- Invocation : cercle et effet de portail.

Les attaques des gardes, des monstres et des invocations utilisent aussi ces
événements. Une incantation interrompue ne publie pas d'impact de compétence.
Les effets expirent, sont dédupliqués et limités en nombre ; ils ne modifient
jamais les PV ou les inventaires. Les événements hors de la vision de
l'observateur sont filtrés avant envoi.

## Compatibilité et limites

Les identifiants des cartes, les quêtes et les sauvegardes restent conservés.
Les palettes et associations de corps/armes existantes alimentent les modèles
stylisés. Le Sprite Maker continue à éditer les assets pixel et leurs
associations ; ce n'est pas un éditeur de maillages 3D.

Le rendu 3D nécessite WebGL. Si son initialisation échoue, le rendu SVG permet
de continuer à utiliser le jeu. Le chargement des assets et le moteur solo
Windows restent hors ligne. Aucun hébergement ou service 3D externe n'est ajouté.
Les performances sur téléphones anciens et avec 40 joueurs restent à mesurer.

## Vérification locale

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_free_movement.py test/test_combat_visuals.py test/test_tactics.py -q
node scripts/verify_scene3d.cjs
node scripts/verify_motion_client.cjs
.\.venv-reprise\Scripts\python.exe -m scripts.verify_living_world_browser --attack-sync
.\.venv-reprise\Scripts\python.exe scripts/verify_living_world_browser.py --3d
.\.venv-reprise\Scripts\python.exe scripts/verify_living_world_browser.py --jitter
.\.venv-reprise\Scripts\python.exe scripts/verify_living_world_browser.py --zone-transitions
node scripts/verify_free_controls.cjs
node scripts/verify_desktop.cjs --packaged
```

Le scénario navigateur utilise une base temporaire et bloque le réseau externe.
Il vérifie de vrais maillages WebGL, un déplacement entre cellules, l'arrêt au
relâchement, l'angle fixe, le refus serveur d'une attaque trop lointaine, puis les
animations d'attaque, d'incantation et de compétence résolue.
Il retarde aussi volontairement une commande de mouvement de 500 ms pour vérifier
la réponse visuelle avant la réponse moteur, sans modification de la position
serveur, puis vérifie l'attaque et l'incantation pendant la marche ralentie.
