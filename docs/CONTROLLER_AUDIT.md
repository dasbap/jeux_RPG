# Périmètre du contrôleur — 0.11.0a19

L’examen porte sur les modules de contenu, classes, compétences, mobs, succès, quêtes et l’intégration des cartes dans le contrôleur. Les fichiers du monde fournis et l’équilibrage des classes existantes sont conservés.

| Module | Améliorations / vérifications | Limites actuelles |
| --- | --- | --- |
| Succès | Espèce et/ou zone/carte, 12 conditions, victoires répétées, identifiants persistants, titres distincts de la progression, prérequis de quête cohérents | Progression de groupe ; pas de formule ou script arbitraire ; historique ancien de kills non détaillé |
| Quêtes | Conditions niveau/quête/succès, filtres de zone, craft/kill, duplication, cycles et cibles vérifiés, renommages propagés | Tutoriel protégé ; pas de dialogues à branches ni d’objectifs multiples dans une même quête |
| Mobs | Modèles universels, sous-espèces, capacités réutilisées, drops décimaux et multi-tirages, aperçu stats/XP/drops | Invocations et résurrection de mobs non prises en charge par l’IA |
| Classes | Tous les modèles éditables, dont invocations ; progression, énergie, affinités, profils ; aperçu de niveau | Les règles de ressources et les gestionnaires d’effets restent ceux du moteur |
| Compétences | Édition des définitions moteur et créations simples, copies, effets multiples, coûts/scaling/incantation/portée | Une portée personnelle offensive ne permet pas de s’attaquer soi-même ; pas de nouveau code d’effet depuis le catalogue |
| Cartes / builder | Recherche, aperçu/références dans le contrôleur ; outils existants d’assemblage, placements, ponts, spawners et trajets conservés ; validation des références | Une fusion/suppression touchant un objectif nécessite de réaffecter cet objectif avant sauvegarde ; les cartes du tutoriel restent protégées |
| PNJ | Placement graphique, dialogue, suivi, quêtes et renommages vérifiés | Pas d’éditeur d’arbre de dialogue ni de programme comportemental personnalisé |
| Monde | Réglages de progression XP, repop, vision, séjour du marchand | Ratio 1:3 et vitesses du moteur conservés |
| Interface du contrôleur | Recherche dans chaque catalogue, scroll, duplication indépendante, annuler/rétablir, rapports et simulation | Interface Tk ; apparence à vérifier sur une machine avec affichage |
| Sauvegarde | Validation avant écriture, quatre catalogues, rollback des erreurs détectées | Pas de transaction système garantie en cas de coupure brutale ; redémarrage du serveur nécessaire |
| Forge / équipements | Les objectifs et aperçus utilisent les recettes existantes | Recettes, emplacements, effets d’équipement et catalogue de matériaux sans éditeur dédié à ce stade |

Les tests couvrent les combinaisons cible/zone/carte, victoires complètes et entraînements, collisions de titres, renommages, sauvegarde/relecture, dépendances, duplication, annuler/rétablir et effets/compétences du catalogue. Les tests du moteur utilisent un monde de référence figé dans `test/fixtures/reference_world` pour rester indépendants des modifications de contenu. Un test distinct ouvre les catalogues actuels de `maps`, valide leurs références et construit les mobs de tous les spawners. Un parcours HTTP avec deux joueurs vérifie le jeu installé avec le monde de référence. Aucun nouveau benchmark à 30 joueurs n’est déduit de cette revue du contrôleur.
