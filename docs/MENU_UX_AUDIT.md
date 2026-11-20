# Vérification des menus — 18 novembre 2026

Contrôle direct avec Chromium local et base SQLite temporaire. Le scénario
reproductible est `python -m scripts.verify_equipment_browser`.

| Point examiné | Correction et contrôle |
| --- | --- |
| Cohérence des menus | Style commun pour Personnage, Équipement, Inventaire, Quêtes, Carte, Bestiaire, Succès, Social et Options ; forge, connexion, personnages et discussion reprennent les mêmes couleurs et composants. |
| Doubles titres et icônes | Masquage du titre de conteneur redondant ; suppression des anciennes icônes CSS qui doublaient les SVG. |
| Quêtes | Les principales ne sont plus étiquetées facultatives ; la récompense XP apparaît une seule fois par fiche. |
| Panoplies | Les valeurs de paliers viennent du catalogue serveur, y compris sans pièce portée. Même composant dans équipement, inventaire et forge ; états et projection de la prochaine activation. |
| Inventaire | Équipement et ressources réunis, filtres et recherche ; état porté/réserve explicite. |
| Bestiaire | Une fiche agrandie pour la sélection, liste latérale des créatures ; statistiques de référence séparées du butin et des capacités. |
| Tri | A/Z trie les noms des créatures et conserve la sélection tant qu'elle reste visible. |
| Navigation | Changer de menu revient en haut et place le focus sur son titre ; sélectionner une créature conserve le focus sur son bouton. |
| Mobile | Neuf menus contrôlés à 390 × 844 ; bandeau des créatures défilant ; pas de débordement horizontal de page ou de fenêtre. |
| Structure | Identifiants HTML uniques et un seul menu visible à la fois. |
| Animations | Réduction des mouvements respectée pour les animations CSS des menus. |

Le parcours contrôlé couvre aussi déséquiper, équiper, remplacer le torse,
recharger la page et retrouver les objets sauvegardés. Les captures restent
locales sous `.data/menu-*.png`.
