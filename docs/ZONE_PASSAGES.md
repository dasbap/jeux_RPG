# Passages entre zones et Lisière

La carte détaillée des zones affiche en rouge les passages physiques vers une autre zone. Le libellé indique la destination et la carte de départ. Un clic rejoint la sortie à pied lorsque le personnage se trouve sur cette carte ; sinon, le message précise quelle carte rejoindre d’abord. Aucune téléportation ni ouverture automatique de l’atlas n’est ajoutée.

La mini-carte reprend la distinction : rouge pour une autre zone, jaune pour un passage interne. Les repères rouges et leurs boutons permettent aussi de marcher jusqu’à la sortie. Les actions sont utilisables au clavier.

L’audit de la Lisière a corrigé deux problèmes :
- Le passage vers Rosée rejoint désormais les remparts avec un retour physique réciproque.
- L’entrée de la grotte conduit au Seuil des Oubliés, avec un retour vers la Lisière. La sortie depuis le Trône de l’Oubli reste à sens unique : entrer par la Lisière ne permet plus de contourner le labyrinthe et d’atteindre directement le boss.

Le passage vers le campement gobelin appartient toujours à la zone Lisière. Le Col des Guetteurs reste accessible dans les deux sens. Les couloirs d’accès ont été dégagés et toutes les entrées/sorties sont vérifiées par `map_playability.issues`.

Sources : `projects/authored/`, export vers `jeuxRPG/maps/`. L’auteur reproductible `scripts/refine_lisiere.py` conserve les identifiants des cartes et routes existantes. Les repères sont calculés depuis les sorties physiques et les zones logiques par `zone_navigation.py`.

Vérification : `python -m pytest test/test_zone_navigation.py`, puis `python -m scripts.verify_coaches_browser --passages`. Le scénario navigateur utilise une base temporaire et vérifie la couleur des sorties, les destinations, l’affichage mobile, la marche jusqu’à la porte et la sauvegarde dans la première salle de la grotte.
