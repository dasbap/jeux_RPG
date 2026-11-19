# Raccourcis clavier

Les contrôles s'appliquent au client web et au solo, en 2D comme en 3D.
L'interface **Options → Raccourcis clavier** permet de remplacer une touche,
annuler la capture avec Échap et restaurer les valeurs par défaut.
Le profil est conservé dans le stockage local du navigateur, sous
`rpg-keybindings-v1`. Deux actions ne peuvent pas utiliser la même touche.
Les touches de déplacement et Échap/Entrée restent réservées.

| Touche | Action |
| --- | --- |
| ZQSD / WASD / flèches | Déplacement |
| Espace | Attaque simple |
| Tab / Maj + Tab | Cible ennemie suivante / précédente |
| F | Parler au PNJ proche ou examiner un objet |
| I | Inventaire |
| E | Équipement |
| J | Journal de quêtes |
| M | Carte |
| B | Bestiaire |
| C | Personnage |
| O | Options |
| P | Social (en ligne) |
| U | Succès |
| T | Discussion (en ligne) |
| R | Recentrer la caméra |
| 1 / 2 / 3 | Compétence offensive / renforcement / affaiblissement favoris |
| H | Aide et configuration des touches |
| Échap | Menus / retour au jeu ; fermeture d'un dialogue |

Les chiffres utilisent la rangée physique `Digit1` à `Digit3` pour fonctionner
sans Maj sur AZERTY. Les lettres utilisent le caractère du clavier. Les actions
ne se répètent pas en maintenant une touche. Les menus peuvent être refermés
avec leur propre raccourci.

Le ciblage commence par l'ennemi vivant le plus proche et parcourt les ennemis
par distance, avec un ordre stable en cas d'égalité. Les créatures neutres sont
exclues tant qu'elles ne sont pas provoquées. Une cible unique reste sélectionnée.

Les raccourcis sont ignorés dans les champs de saisie, les textes modifiables,
les listes déroulantes et les dialogues ouverts. Les modificateurs du navigateur
et la composition IME restent disponibles. Espace conserve l'activation native
d'un bouton qui possède le focus. Dans les menus, Tab garde la navigation native.
Ouvrir un menu ou le chat arrête le mouvement local ; le maintien d'une direction
s'interrompt aussi pendant la saisie.

Les raccourcis réutilisent les actions existantes : `RPGScene3D.attack`,
`selectEntity`, `tutorialCommand("talk")`, les boutons de compétences et `showView`.
Ils ne changent pas les règles de portée, les temps de recharge ou les prérequis.
Le moteur reste responsable de leur validation. L'aide du HUD et les attributs
accessibles des menus reflètent les touches personnalisées.

Vérification :

```powershell
node --test scripts/verify_keybindings.cjs scripts/verify_free_controls.cjs scripts/verify_motion_client.cjs scripts/verify_scene3d.cjs scripts/verify_sprites.cjs
python -m scripts.verify_cave_browser --keyboard
```

Le scénario navigateur utilise des vues produites par le moteur et le vrai client
WebGL. Les actions sont observées à l'entrée du répartiteur de commandes ;
il vérifie ciblage, attaque, dialogue, menus, saisie et persistance après reload.
Captures : `.data/keybindings-desktop.png` et `.data/keybindings-mobile.png`.
