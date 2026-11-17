# Calculs côté client, décisions vérifiées côté serveur

Le client du jeu réalise autant de calculs que possible. Il reste une source
non fiable : un joueur peut remplacer entièrement son navigateur et fabriquer
ses requêtes. Cette règle concerne le mode multijoueur ; le solo hors ligne
exécute volontairement son propre moteur local.

## Répartition actuelle

| Travail | Client | Serveur |
| --- | --- | --- |
| Carte, caméra, sprites, animation, orientation | Calcule et affiche | Fournit les données du catalogue et l'état réel |
| Menus, filtres du bestiaire, sélection | Calcule localement | Vérifie à nouveau toute action qui modifie la partie |
| Chemin tactique d'un joueur ou d'une invocation contrôlée | Recherche le chemin et l'envoie | Vérifie chaque pas, la destination, les obstacles, les coins diagonaux, la longueur et les droits de contrôle |
| Itinéraire entre les zones | Recherche et propose l'itinéraire | Vérifie les liaisons et les zones connues ; calcule les délais réels du trajet |
| Vitesse, immobilisation, incantation, délais d'action | Affiche les compteurs | Décide avec son horloge et son état |
| Dégâts, PV, mort, XP, butin, monnaie, équipement | Affiche le résultat | Calcule et applique les résultats |
| PNJ, gardes, raids et monde partagé | Affiche et anime | Décide des actions et de la progression du monde |
| Sauvegardes multijoueurs | Peut conserver un cache d'affichage | Persiste l'état vérifié avec le mécanisme de sauvegarde et de fencing |

La recherche des chemins des joueurs est **déjà déportée** : `gridPath()` dans
le navigateur, puis `_battle_move()` ou `_validate_unit_routes()` pour la
vérification. Le serveur n'effectue pas une seconde recherche du chemin reçu.
Pour les déplacements entre zones, `proposed_path()` utilise également le
trajet vérifié du client ; l'ancien mode sans proposition garde son calcul
serveur pour compatibilité.

## Frontière de confiance

Le client propose ses actions et, pour le contrôle libre, ses positions.
Le moteur accepte une position seulement après validation de la vitesse avec
son horloge, du terrain et des contraintes du personnage. Les états ordinaires
ne corrigent plus une marche légale. Le crédit inutilisé pour le retard réseau
est borné ; changer de direction ou envoyer davantage de requêtes ne le recharge pas.

Les chemins `walk` et les ordres d'invocations gardent leur exécution dans le
moteur. Les dégâts, les gains et les délais d'action ne sont jamais acceptés
sur simple déclaration du client.

Le format de commande est limité aux champs attendus ; ajouter `hp`, `gold`,
`damage` ou un délai fabriqué n'autorise pas leur modification. Les validations
dans l'interface servent au confort ; leur suppression ne doit pas contourner
les vérifications du moteur.

Le protocole de bundles évite de retransmettre certains blocs inchangés. Ses
empreintes servent au cache et à la synchronisation, pas à prouver que le client
est honnête. Les secrets serveur ne font pas partie des assets du client.

## Règle pour les optimisations suivantes

1. Déplacer côté client le rendu, les recherches et les prévisualisations qui
   ne modifient pas l'état partagé.
2. Pour une proposition qui modifie la partie, conserver une vérification
   serveur bornée, moins coûteuse que la recherche initiale.
3. Si vérifier un résultat exige de refaire toute la simulation, conserver cette
   simulation côté serveur. La doubler sur le client n'économise pas son CPU.
4. Accepter les positions du contrôle libre après validation de vitesse et de
   terrain, sans recaler une marche légale sur une seconde simulation concurrente.
5. Ne jamais confier l'horloge du monde ou les résultats d'un raid au joueur qui
   est connecté : sa déconnexion ou son navigateur modifié ne doivent pas lui
   donner le contrôle de la simulation.

Le monde vide continue à utiliser les événements planifiés et le rattrapage
borné. Les simulations détaillées sont réservées aux rencontres actives. Cette
répartition réduit le travail utile du serveur mais ne certifie pas, à elle
seule, la tenue des quotas gratuits de Vercel ni 40 joueurs simultanés.

## Vérification locale

```powershell
.\.venv-reprise\Scripts\python.exe -m pytest test/test_client_work_boundary.py test/test_tactics.py test/test_tutorial.py -q
```

Les tests de cette frontière interdisent la recherche serveur d'un chemin
tactique proposé et vérifient le rejet de commandes transportant des résultats
fabriqués. Les suites tactiques et de voyage couvrent déjà téléportation,
obstacles, accélération, portée et contrôle d'unités.
