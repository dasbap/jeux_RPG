# Quêtes et équipements facultatifs

L’exploration et l’accès aux régions ne nécessitent pas de terminer une quête. La quête « Protéger la lisière » de Mira débloque spécifiquement **la forge du village de Rosée** après remise de la quête. Un objectif rempli sans retour auprès de Mira ne suffit pas. Ce verrou est appliqué côté serveur, pour fabriquer comme pour améliorer.

Le projet contient 26 quêtes : les 14 contrats de combat et d’artisanat réécrits, plus 12 quêtes de récit, d’exploration et de service. Parler à un personnage ouvre une conversation ; chaque contrat s’accepte et se rend séparément. Le journal permet de filtrer et de suivre les objectifs, et conserve les indices. Les suites restent facultatives : les perfectionnements demandent la remise de la fabrication correspondante, et la chasse au chef demande la remise de la première quête de Mira. Ces dépendances ne verrouillent pas l’exploration. Voir [l’histoire intégrée](HISTOIRE_IMPLEMENTATION.md).

| Nouvelle espèce | Niveau | Carte et placements | Matériaux garantis par créature | Équipement associé | Quête d’amélioration |
| --- | --- | --- | --- | --- | --- |
| Luciole cuirassée | 1 | Prairies des Lucioles, 3 spawners | Carapace de luciole, poudre lumineuse | Bottes des Lucioles : PV, endurance, sagesse | Atteindre +1 |
| Sanglier roncier | 3 | Verger des Ronces, 3 spawners | Cuir de sanglier roncier, épine roncière | Gants des Ronces : PV, force, endurance | Atteindre +1 |
| Gardien de schiste | 5 | Carrière des Échos, 1 spawner | Plaque de schiste, cœur minéral | Casque de Schiste : PV, endurance | Atteindre +2 |
| Veilleur des brumes | 7 | Ruines de la Veille, 3 spawners | Étoffe de veille, essence de veille | Manteau de la Veille : PV, intelligence, sagesse | Atteindre +2 |

Chaque espèce a ses statistiques et sa capacité propres. Les apparitions existantes sont conservées. Les nouveaux emplacements sont accessibles depuis les arrivées de la carte et restent à distance des passages et PNJ. Les corps doivent être dépecés pour récupérer les matériaux.

Mira propose les patrouilles de la Lisière ; Sève, les lucioles et les sangliers ; Néran, le Gardien de schiste. Élyne propose la chasse aux Veilleurs à Brume. Garrik propose les quatre fabrications et leurs perfectionnements. Les recettes utilisent les matériaux de leur espèce ; les coûts d’amélioration suivent les règles de la forge.

Les quêtes d’amélioration portent sur un palier précis, pas sur le nombre de clics. Un équipement déjà fabriqué ou amélioré est reconnu à l’acceptation, puis la récompense se récupère auprès du donneur, une seule fois. Les autres équipements n’avancent pas cet objectif. Remplir un compteur ne suffit pas à débloquer la suite : il faut rendre la quête précédente au PNJ. Les prérequis sont éditables dans le Builder, formulaire de quête puis « Prérequis », liste « Quêtes terminées ». Les références inexistantes et les cycles sont refusés à la validation.

Les définitions sont présentes dans `jeuxRPG/maps` et `projects/authored`, et restent éditables dans le contrôleur/Builder. La vérification reproductible des catalogues livrés se lance avec `python scripts/verify_optional_content.py`.

La **Panoplie de la Lisière** réunit le casque, la veste, les gants, les jambières,
les bottes et la ceinture de la Lisière. Les paliers sont cumulatifs et comptent
les emplacements distincts équipés sur un même personnage.

| Pièces équipées | Bonus ajouté à ce palier |
| --- | --- |
| 2 | +4 PV, +1 endurance |
| 4 | +2 force, +2 intelligence, +1 sagesse |
| 5 | +8 PV, +2 endurance, +2 sagesse |

À 5 ou 6 pièces, le total est donc +12 PV, +3 endurance, +2 force,
+2 intelligence et +3 sagesse. Remplacer une pièce retire les paliers perdus.
Améliorer une pièce ne recompte pas son bonus de panoplie. Les anciennes
sauvegardes équipées reçoivent les bonus une seule fois au chargement.

Le Builder propose l’onglet **Panoplies** pour les noms et bonus des trois paliers.
Le champ **Panoplie** de **Forge / recettes** associe chaque recette à son ensemble.
L’interface Équipement affiche le nombre de pièces, les paliers actifs ou inactifs
et le bonus cumulé ; la forge indique l’appartenance de chaque recette.

Pour vérifier aussi les boutons de la forge et les filtres du journal, générer les scènes avec `python scripts/verify_optional_content.py --ui-fixtures .data/quest-ui.json`, puis lancer `node scripts/verify_quest_ui.cjs .data/quest-ui.json`.
