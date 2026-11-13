# Onglet Interface du Builder

Ouvrir le contrôleur du projet puis sélectionner **Interface** dans la liste **Catalogue** ou dans les onglets. Cet éditeur règle la présentation du jeu à partir du projet Builder.

## Réglages disponibles

| Groupe | Réglages |
| --- | --- |
| Menus | Largeur et hauteur en pourcentage de l’écran ; position centrée, à gauche ou à droite |
| Quêtes | Largeur minimale des fiches, marges, espacement, présentation compacte ou aérée |
| Mini-carte | Largeur et hauteur sur grand écran ; les petits écrans gardent leur disposition adaptée |
| Couleurs et texte | Couleur d’accent des actions, fond des menus, texte, taille de base de la police |
| Informations | Durée d’affichage du nom de zone à l’entrée |

L’aperçu schématique s’actualise pendant la saisie. Il montre les proportions des menus, les couleurs, les fiches et la mini-carte ; le rendu exact dépend de la résolution du jeu.

## Appliquer et conserver

1. Modifier les champs du groupe souhaité. **Choisir…** ouvre le sélecteur de couleur.
2. Cliquer **Appliquer à l’interface**. Les valeurs sont validées et ajoutées à l’historique du projet.
3. Cliquer **Enregistrer le projet** dans la barre du Builder.
4. Reconstruire Windows pour mettre à jour le client solo embarqué, ou redémarrer le serveur pour appliquer les réglages au jeu en ligne.

**Annuler modification** et **Rétablir** agissent aussi sur ces réglages. **Valeurs par défaut** restaure les réglages d’interface ; cette modification peut être annulée. **Recharger les réglages du projet** abandonne les saisies non appliquées de cet onglet.

Les valeurs actuelles par défaut conservent les grands panneaux à 75 % de la largeur et de la hauteur, centrés, et les fiches de quête compactes. La liste de l’engrenage reste petite et défilante : le grand panneau s’ouvre après le choix d’une option. Le HUD est masqué pendant la consultation, puis réapparaît avec le bouton Retour. Les anciens projets reçoivent ces valeurs sans nécessiter une migration manuelle.

Les réglages sont enregistrés dans la section `content.interface` de `projects/authored/content.json`, puis exportés dans les catalogues livrés au jeu. Les limites, types de champs et couleurs sont validés avant l’enregistrement. Aucun CSS ou JavaScript arbitraire n’est exécuté depuis ces champs.

Vérifications : `python -m pytest test/test_interface_builder.py -q` contrôle notamment le véritable onglet Tk, la sauvegarde, l’annulation et la transmission des réglages. `node scripts/verify_interface_ui.cjs .data/ux-audit/fixtures.json` contrôle leur effet dans le navigateur avec une politique CSP stricte, si les fixtures UI et Playwright sont installés.
