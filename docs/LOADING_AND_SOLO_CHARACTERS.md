# Chargements et personnages solo

Les transitions principales affichent un écran dédié : démarrage solo ou en ligne,
connexion au compte, création et sélection de personnage, ouverture de sa liste,
lancement d'une aventure et arrivée dans une nouvelle zone. Le démarrage solo
publie ses étapes réelles depuis le Worker : sauvegarde locale, moteur Python /
WebAssembly, contenu du monde, puis restauration des personnages. La progression
reste indéterminée ; aucun pourcentage artificiel n'est affiché.

Le contrôleur `RPGLoading` conserve les tâches actives : terminer une ancienne
tâche ne masque pas une transition plus récente. Le contenu principal est marqué
occupé et temporairement inerte. Les commandes clavier et le joystick sont bloqués
pendant le chargement. Les écrans se ferment aussi en cas d'erreur, qui reste
visible via le message habituel du jeu. L'animation respecte la préférence de
réduction des mouvements.

Une arrivée de zone conserve les directions déjà maintenues : le mouvement peut
reprendre après le rendu, avec la position d'arrivée validée. Un changement de
personnage ou de mode arrête le mouvement. Les rafraîchissements ordinaires du
combat ne déclenchent pas l'écran de chargement.

## Personnages

Le même sélecteur sert au solo et au multijoueur, avec **un personnage par classe**.
Chaque carte indique le nom, la classe et le dernier personnage joué. Le formulaire
permet de créer un autre personnage dans une classe disponible. La liste est
accessible directement par **Menus → Mes personnages**, ainsi que dans Options.
Au démarrage solo, une sauvegarde avec plusieurs personnages ouvre cette liste ;
un personnage unique peut reprendre automatiquement son aventure.

Les personnages solo restent dans la base IndexedDB existante. Le format de
sauvegarde ne change pas. Leurs aventures, niveaux, quêtes, inventaires et or sont
propres à chaque personnage ; les personnages du multijoueur restent sur le compte
en ligne.

Changer de personnage suspend le flux solo, sauvegarde l'aventure précédente,
sélectionne le personnage demandé et charge son état avant d'afficher le jeu.
Les caches du personnage précédent sont vidés. Les mises à jour tardives dont
l'identifiant ne correspond pas au personnage choisi sont ignorées. Une erreur
laisse la sélection accessible, avec un message, sans écran bloqué.

## Vérification

```powershell
python -m pytest -q test/test_browser_solo.py
node --test scripts/verify_loading_characters.cjs scripts/verify_solo_menu.cjs scripts/verify_solo_resume.cjs scripts/verify_free_controls.cjs scripts/verify_touch_controls.cjs
node scripts/verify_solo_browser.cjs
```

Le dernier scénario utilise le moteur WebAssembly réel, des ressources Pyodide
locales et une API en ligne indisponible. Il contrôle deux personnages de classes
différentes, leurs aventures distinctes, le passage de l'un à l'autre, leur présence
après rechargement et les écrans ordinateur/mobile. Il utilise un contexte navigateur
isolé. Les captures sont dans `.data/loading-solo.png`, `.data/solo-characters.png`
et `.data/solo-characters-mobile.png`.
