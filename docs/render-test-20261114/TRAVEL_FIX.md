# Progression et sauvegarde des trajets sur Render

Deux défauts ont été corrigés sur le seul service Render de test :

- `89f9969` : le transport des états WebSocket omettait `travel_progress` et les
  noms du départ, de l'étape et du but. Le moteur avançait, mais le panneau
  pouvait remettre son curseur au départ et garder le temps total affiché.
- `578daea` : une arrivée entre deux points d'une même zone ne modifiait pas la
  signature de sauvegarde. `tutorial.arrive` incrémente maintenant le point de
  sauvegarde déjà pris en charge par le moteur. La position d'arrivée et la fin
  du trajet sont ainsi capturées, sans sauvegardes répétées à l'arrêt.

## Vérification

Le test navigateur réel utilise un compte fictif préparé pour la recette,
indépendant du personnage de l'utilisateur. Sur le trajet forêt → Rosée,
le curseur a avancé de 86,3 % à 100 %, le compte à rebours de 2 à 0 secondes,
puis le panneau s'est fermé à l'arrivée. Aucune erreur JavaScript n'a été relevée.

Une lecture indépendante du D1 isolé, ciblée sur cette session fictive, confirme
la position `rosee`, l'absence de trajet en cours et le nouveau point de
sauvegarde. Les mesures sont dans `travel-progress.json`.

Le test de régression de sauvegarde échouait avant le correctif : aucune mise à
jour du tutoriel n'était préparée après une arrivée dans la même zone. Il passe
maintenant et vérifie également la restauration depuis le snapshot et l'absence
de réécritures lors de captures inchangées. Les contrôles ciblés totalisent
46 tests Python réussis, un test Redis ignoré et 15 tests d'interface réussis.
La construction Docker et les validations GitHub Actions ont réussi.

Le site de production Vercel et le client de bureau ne sont pas redéployés.
