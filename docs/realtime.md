# Temps réel et sauvegardes

L'entrée Vercel est une application ASGI FastAPI. Le navigateur de production utilise `/api/ws` pour les commandes et reçoit les changements d'état par WebSocket. Les routes HTTP restent compatibles et passent par le même moteur en mémoire.

Le moteur calcule les combats dans une base SQLite en RAM. Turso est chargé au démarrage du moteur, puis utilisé pour les sauvegardes. Les lectures d'état, les déplacements, les pertes de PV, les cooldowns et les changements de salle dans une même zone ne consultent pas Turso et ne déclenchent pas de sauvegarde.

Un changement d'inventaire, d'équipement, d'XP, de niveau, une quête acceptée ou complétée, un changement de zone ou un marqueur de checkpoint automatique capture un point de sauvegarde. La première modification ouvre une fenêtre fixe de cinq secondes. Les modifications suivantes remplacent les lignes concernées dans le même lot, sans repousser indéfiniment la sauvegarde. Le point capturé ne suit pas les déplacements ultérieurs dans la même zone.

Les comptes, les modifications administratives, la création d'une partie et ses participants sont également conservés. Une sauvegarde échouée reste en attente et est retentée après cinq secondes. Les comptes et les parties existants sont repris sans migration destructive du schéma.

Redis élit un moteur faisant autorité avec un bail renouvelé toutes les huit secondes. Les joueurs connectés à cette instance échangent directement avec sa RAM. Les autres instances relaient les requêtes et réponses en lots au maximum toutes les 500 ms par canal actif. Il n'y a aucun `SET` ni `PUBLISH` pour chaque frame : les publications sont regroupées, et les canaux inactifs ne publient rien. Le cache Redis est initialisé au premier démarrage, puis les snapshots sont écrits seulement lors des sauvegardes utiles. Redis consomme donc encore des commandes de coordination et, lorsqu'une partie est répartie entre instances, des commandes de relais.

Le moteur libère son rôle après la fermeture du dernier WebSocket local et à la fin d’une requête HTTP isolée, pour éviter qu’une instance inactive garde la partie. Le cache Redis indique si un lot reste à écrire : une reprise d’un checkpoint déjà enregistré ne réécrit pas Turso. Le bail expire après trente secondes. Une instance qui ne peut plus renouveler son bail cesse de traiter les commandes après vingt-cinq secondes. Les snapshots Redis et les écritures Turso sont protégés contre un ancien moteur : vérification du propriétaire dans Redis et numéro de génération dans la transaction Turso. Une reprise recharge le dernier checkpoint, pas les déplacements non sauvegardés. Une panne avant la capture du lot peut perdre les changements des cinq dernières secondes.

Les connexions WebSocket se reconnectent automatiquement avec un délai progressif et se réabonnent. Les snapshots utilisent les bundles existants pour éviter de renvoyer les cartes et catalogues inchangés. Les connexions sont renouvelées avant la limite d'exécution Vercel. L'origine et l'hôte sont vérifiés ; les jetons restent dans les messages authentifiés, jamais dans l'URL ni dans les logs.

Variables de production : `REDIS_URL` ou `KV_URL`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `RPG_ADMIN_TOKEN`. Fluid Compute doit être activé. Les rafraîchissements renvoient `X-RPG-Runtime: memory` et `Server-Timing` avec zéro échange distant. `X-RPG-Save-Pending` indique un lot en attente, et `X-RPG-Save-Count` les lots terminés par le moteur courant.

Le workflow de publication teste deux instances avec Redis réel avant le déploiement, puis vérifie en production le WebSocket, le tutoriel, la sauvegarde et les lectures d'état sans appel à Turso. Le forfait gratuit reste soumis aux quotas CPU, mémoire, transfert et commandes des fournisseurs.

## Commandes mobiles et budget réseau

Le joystick est calculé dans le navigateur. Il regroupe les mouvements du doigt, limite les intentions de déplacement à quatre par seconde et réutilise une trajectoire déjà en cours. Une position identique ne déclenche pas une nouvelle commande dans la même direction. Le relâchement annule la trajectoire avec une seule commande. Les attaques et sorts utilisent les mêmes fonctions et le même moteur autoritaire que les déplacements ; aucun serveur distinct n'est ajouté.

Avec WebSocket, les actions ne déclenchent plus une demande `/api/state` supplémentaire : l'état vient des mises à jour poussées. Un onglet masqué suspend ces mises à jour ; les messages de visibilité et de maintien de connexion sont traités localement, sans relais Redis. Sur l'instance qui détient le moteur, les actions et lectures restent en RAM. Sur les autres instances, le relais conserve ses lots de 500 ms ; Redis n'est pas écrit à chaque mouvement du doigt. Les quotas dépendent encore du nombre d'instances, des joueurs actifs et de la durée des parties.

Le ciblage automatique privilégie les ennemis attaquables, change de cible lorsqu'elle devient inaccessible ou meurt, et choisit une cible propre à chaque soin ou compétence. Le bouton « Ciblage auto » permet de quitter une sélection manuelle. Les décisions de ciblage sont locales et ne provoquent aucune requête supplémentaire.
