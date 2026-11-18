# Dépeçage et réapparition progressive

## Touches

- **X** : cibler le prochain corps contenant du butin, en commençant par le plus proche.
- **Maj + X** : parcourir les corps dans l’autre sens.
- **G** : dépecer le corps ciblé à portée, ou le corps dépeçable le plus proche à portée si aucun corps valide n’est ciblé. Si la cible est distante, le personnage s’en approche ; appuyer de nouveau à portée.

Les touches se modifient dans Options → Raccourcis clavier. Les anciens raccourcis personnalisés sont conservés ; les nouvelles actions reçoivent une touche libre en cas de conflit. Les corps vides ou déjà dépecés sont ignorés. Le moteur contrôle la position, la portée, les incantations et l’unicité du butin partagé, y compris en multijoueur.

## Spawners

Le profil **default / Standard** a un cycle de **120 secondes réelles**. L’intervalle est le cycle divisé par l’effectif du spawner : quatre créatures donnent une réapparition toutes les 30 secondes, jusqu’à quatre créatures vivantes au maximum. Un spawner plein ne stocke pas de crédit : le prochain cycle commence à la mort suivante.

Les délais commencent à la mort, restent enregistrés dans la sauvegarde et continuent lors des changements de carte. Au retour, le moteur rattrape les apparitions dues sans dépasser l’effectif. Une créature qui poursuit le joueur sur une autre carte reste comptée ; elle n’est pas dupliquée à son origine.

Le Builder propose **Réapparition / profils** pour modifier les durées communes. Préréglages livrés : Standard, Guerrier et Archer 120 s ; Mage 150 s ; Élite 240 s ; Boss 600 s ; Civil / neutre 120 s ; aucune réapparition 0 s. Les boss existants utilisent le profil Boss. Les autres spawners héritent du profil adapté ou de Standard.

Dans l’outil Spawner, choisir un profil rapide ou renseigner un cycle personnalisé. Une durée vide hérite du profil ; **0 désactive la réapparition**. Le formulaire affiche le délai effectif par créature. Changer le profil dans le sélecteur efface la durée personnalisée pour appliquer le profil choisi.

L’ancien réglage global `world.repop_seconds` reste disponible pour les catalogues historiques sans profils. Les profils publiés remplacent ce mécanisme de remplissage instantané après absence. Changer uniquement une durée ou un profil ne réinitialise pas les créatures déjà vivantes.

Vérifications : `pytest test/test_spawn_cycles.py`, `node --test scripts/verify_keybindings.cjs`, `python -m scripts.verify_coaches_browser --harvest`. Le scénario navigateur vérifie ciblage, approche, dépeçage, absence de double butin et persistance de l’inventaire.
