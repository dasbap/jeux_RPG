# Équipement, quêtes et bestiaire

Le menu **Équipement** permet de sélectionner un emplacement, de rechercher une
pièce et de comparer ses cinq bonus à la pièce portée. **Déséquiper** place la
pièce dans la réserve du personnage ; **Équiper** échange les pièces du même
emplacement. Leur niveau d'amélioration est conservé, y compris après fermeture
du jeu. La fabrication d'une pièce de remplacement conserve aussi l'ancienne.
La forge peut améliorer une pièce en réserve sans appliquer ses bonus au porteur.
L'inventaire réunit désormais équipement et matériaux, avec recherche et filtre.
Les fiches d'objets utilisent les mêmes bonus de panoplie dans l'équipement,
l'inventaire et la forge : valeurs par palier, nombre de pièces portées, état
actif/inactif et activation prévue avec la nouvelle pièce. Les bonus de la pièce
seule sont distingués des bonus de panoplie.

Le moteur refuse les changements pendant un trajet, une incantation, un combat
de rencontre ou une alerte hostile en exploration, et lorsque le personnage est
à terre. Les bonus de pièces et de panoplies sont recalculés. Changer de tenue
ne restaure pas les points de vie.

Le **Journal de quêtes** propose une recherche, les catégories et les types,
ainsi que les états Toutes / En cours / À rendre / Terminées. Le bouton Suivre
conserve le repérage de l'objectif. Le **Bestiaire** affiche uniquement les
créatures découvertes. La créature sélectionnée apparaît en grand, avec sa fiche
complète : caractéristiques de référence, butin, capacités, habitats et résistances.
Les autres créatures restent sélectionnables dans une liste latérale, transformée
en bandeau défilant sur mobile. Le tri A/Z porte sur leurs noms.

Les menus s'adaptent aux petits écrans et au réglage système de réduction des
animations. Les filtres et les fiches ouvertes restent stables lorsque les
données affichées ne changent pas.

Contrôles locaux :

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest -q test/test_equipment_management.py test/test_equipment_sets.py test/test_tutorial.py
node --test scripts/verify_equipment_ui.cjs scripts/verify_bestiary.cjs
.\.venv-reprise\Scripts\python.exe -m scripts.verify_equipment_browser
```

Le dernier scénario utilise un compte fictif et une base SQLite temporaire,
vérifie les commandes depuis Chromium, recharge la page et écrit les captures
dans `.data/menu-*.png`. Il contrôle aussi les neuf menus sur ordinateur et mobile,
les identifiants uniques, l'absence de débordement horizontal et les panoplies
dans les trois écrans. Il ne modifie aucune sauvegarde existante.
