# Temps réel et sauvegardes

L'entrée Vercel est une application ASGI FastAPI. Le navigateur de production utilise `/api/ws` pour les commandes et reçoit les changements d'état par WebSocket. Les routes HTTP restent compatibles et passent par le même moteur en mémoire. La production utilise Cloudflare D1 depuis le 6 novembre 2026 ; voir [l’architecture actuelle](ARCHITECTURE.md) et [les preuves de bascule](D1_PRODUCTION.md).

Le moteur calcule les combats dans une base SQLite en RAM. Cloudflare D1 est chargé à la prise de rôle du moteur, puis utilisé pour les sauvegardes via un Worker privé. Les lectures d'état, les déplacements, les pertes de PV, les cooldowns et les changements de salle dans une même zone ne consultent pas D1 et ne déclenchent pas à eux seuls de sauvegarde.

Un changement d'inventaire, d'équipement, d'XP, de niveau, une quête acceptée ou complétée, un changement de zone ou un marqueur de checkpoint automatique capture un point de sauvegarde. La première modification ouvre une fenêtre fixe de cinq secondes. Les modifications suivantes remplacent les lignes concernées dans le même lot, sans repousser indéfiniment la sauvegarde. Le point capturé ne suit pas les déplacements ultérieurs dans la même zone.

Les comptes, les modifications administratives, la création d'une partie et ses participants sont également conservés. Une sauvegarde échouée reste en attente et est retentée après cinq secondes tant que le moteur reste propriétaire. La remise à zéro historique des joueurs de test ne s’exécute pas sur le chargement D1 ; le déploiement fixe `RPG_RESET_TEST_PLAYERS=0`. La coordination D1 possède un espace Redis dérivé de l’URL du Worker, distinct de l’ancien backend.

Redis élit un moteur faisant autorité avec un bail renouvelé toutes les huit secondes. Les joueurs connectés à cette instance échangent directement avec sa RAM. L'inventaire, l'équipement, les quêtes et les combats ne sont plus copiés dans des checkpoints Redis : les lots de sauvegarde vont dans D1 via le Worker. La présence des joueurs est également locale au moteur. Les autres instances relaient les requêtes et réponses en lots programmés toutes les 500 ms par canal actif ; ces réponses peuvent contenir l'état demandé. Ce regroupement n’est pas une garantie de délai maximal en cas de charge ou de panne. Les canaux inactifs ne publient rien.

Le moteur libère son rôle après la fermeture du dernier WebSocket local et à la fin d’une requête HTTP isolée. Le bail expire après trente secondes. Une instance qui ne peut plus renouveler son bail cesse de traiter les commandes après vingt-cinq secondes. Une vérification du propriétaire dans Redis et les protections de génération dans le lot atomique D1 empêchent un ancien moteur d’écraser les sauvegardes. Chaque reprise recharge le backend configuré. Les anciens checkpoints Redis, s’il en reste dans cet espace de coordination, sont persistés avant leur retrait sous le bail courant. Une panne avant la sauvegarde D1 peut perdre les changements encore en RAM. Les cinq secondes sont un échéancier nominal, pas un RPO garanti ; une panne durable du stockage prolonge cette fenêtre. Aucun retour automatique vers Turso n’est effectué.

Les connexions WebSocket se reconnectent automatiquement avec un délai progressif et se réabonnent. Les snapshots utilisent les bundles existants pour éviter de renvoyer les cartes et catalogues inchangés. Les connexions sont renouvelées avant la limite d'exécution Vercel. L'origine et l'hôte sont vérifiés ; les jetons restent dans les messages authentifiés, jamais dans l'URL ni dans les logs.

Variables de production : `RPG_DATABASE_BACKEND=d1`, `RPG_D1_WORKER_URL`, `RPG_D1_SERVICE_TOKEN`, `REDIS_URL` ou `KV_URL` (ou la liste décrite ci-dessous), et `RPG_ADMIN_TOKEN`. Aucun identifiant Turso n’est requis pour le moteur D1. Fluid Compute doit être activé. Les lectures d’état du propriétaire renvoient `X-RPG-Runtime: memory` et `Server-Timing` avec zéro échange distant ; les requêtes passant par un relais utilisent Redis. `X-RPG-Save-Pending` indique un lot en attente, et `X-RPG-Save-Count` les lots terminés par le moteur courant.

Le workflow de publication teste deux instances avec Redis réel avant le déploiement, puis vérifie le WebSocket, le tutoriel, la sauvegarde et les lectures d’état en mémoire. Il exige `database_backend=d1` quand la configuration de publication sélectionne D1. Les consommations de Vercel, Redis, Workers et D1 doivent être mesurées ; les tests fonctionnels ne garantissent pas le respect des quotas.

## Plusieurs URL Redis

`REDIS_URLS` accepte une liste JSON d'URL Redis. `RPG_REDIS_ACTIVE_INDEX` choisit l'entrée active à partir de 0 ; sa valeur par défaut est 0. Cette liste a priorité sur `REDIS_URL` et `KV_URL`. Le moteur, le relais, la présence et les limites de connexion utilisent tous la même entrée. Les autres instances sont des destinations de secours indépendantes, sans réplication automatique.

Pour la production, enregistrer la liste dans le secret GitHub de l'environnement `production` nommé `REDIS_URLS`, puis l'index dans la variable `RPG_REDIS_ACTIVE_INDEX` du même environnement. Exemple de structure avec des valeurs fictives :

```json
["rediss://utilisateur:mot-de-passe@redis-principal:6379", "rediss://utilisateur:mot-de-passe@redis-secours:6379"]
```

L'index 1 sélectionne la seconde entrée. Le workflow synchronise ce secret vers le projet Vercel existant et vérifie l'instance sélectionnée avant publication. Sans liste, les installations actuelles continuent d'utiliser `REDIS_URL` ou `KV_URL`.

Une bascule Redis doit se faire pendant une maintenance, après sauvegarde des changements en attente et arrêt des anciens moteurs. Vérifier la sauvegarde D1 et utiliser une destination Redis neuve pour reprendre depuis le D1 actuel. Les changements encore en RAM ne sont pas transférés entre deux Redis indépendants. La sélection du backend D1, du Worker et de Redis reste identique pour toutes les instances. Ne pas remettre en service l’ancienne base Turso comme raccourci de reprise.

## Commandes mobiles et budget réseau

Le joystick est calculé dans le navigateur. Il regroupe les mouvements du doigt, limite les intentions de déplacement à quatre par seconde et réutilise une trajectoire déjà en cours. Une position identique ne déclenche pas une nouvelle commande dans la même direction. Le relâchement annule la trajectoire avec une seule commande. Les attaques et sorts utilisent les mêmes fonctions et le même moteur autoritaire que les déplacements ; aucun serveur distinct n'est ajouté.

Avec WebSocket, les actions ne déclenchent plus une demande `/api/state` supplémentaire : l'état vient des mises à jour poussées. Un onglet masqué suspend ces mises à jour ; les messages de visibilité et de maintien de connexion sont traités localement, sans relais Redis. Sur l'instance qui détient le moteur, les actions et lectures restent en RAM. Sur les autres instances, le relais conserve ses lots de 500 ms ; Redis n'est pas écrit à chaque mouvement du doigt. Les quotas dépendent encore du nombre d'instances, des joueurs actifs et de la durée des parties.

Le ciblage automatique privilégie les ennemis attaquables, change de cible lorsqu'elle devient inaccessible ou meurt, et choisit une cible propre à chaque soin ou compétence. Le ciblage est automatique par défaut, sans bouton à activer. Les décisions de ciblage sont locales et ne provoquent aucune requête supplémentaire.


## Comptes, équipes et présence

L’inscription utilise un nom de compte unique, insensible à la casse, et un mot de passe de 12 à 128 caractères. Les mots de passe sont hachés avec scrypt (N=131072, r=8, p=1), avec un sel aléatoire. Les sessions opaques expirent après 30 jours ; seuls leurs hashes sont enregistrés. Le navigateur ne présente aucune clé de connexion. Chaque compte possède au maximum un personnage par classe. La sélection d’un personnage s’applique aux sessions du compte ; chaque personnage garde son tutoriel et son inventaire. Les anciennes inscriptions par clé et le PvP sont désactivés en production.

Les demandes d’amis et les invitations d’équipe sont explicites. Une équipe sociale contient quatre comptes au maximum, même si plusieurs invitations sont acceptées simultanément. Chaque personnage voyage dans sa propre session : les déplacements, les quêtes et les salles d’un allié ne déplacent pas les autres. Le chat de groupe utilise l’équipe sociale. Les joueurs de tutoriels différents sont visibles dans la même zone et sur la même carte ; les autres personnages ne sont pas des cibles attaquables.

Social, en haut à droite, présente les alliés, leur zone, leur position et leur serveur. La carte régionale indique leurs zones. Le ralliement nécessite des alliés dans la même zone et le même serveur, en vue sortie hors combat/exploration ; chaque allié accepte ou ignore l’appel. Le bouton Rejoindre trace un trajet vers un allié arrêté. Un trajet peut être mis en attente pour être rejoint en cours de route, avec des rencontres hostiles possibles sur les chemins dangereux. La reprise du trajet est individuelle.

Le réglage Builder `rules.social.realm_capacity` vaut actuellement 40 joueurs actifs par serveur de jeu. Une présence expire après 60 secondes sans lecture d’état. Les onglets d’un même personnage réutilisent cette place. Les connexions WebSocket sont également plafonnées avec ce réglage, par instance de transport et non globalement entre instances. `RPG_RUNTIME_REALMS` accepte 1 à 3 serveurs logiques ; la publication active **1**. Ce paramètre ne fixe pas le nombre d’instances physiques : Vercel reste responsable de l’autoscaling. Ces limites configurées ne certifient pas les performances à 40 joueurs ; voir les [mesures disponibles et leurs limites](ARCHITECTURE.md#mesures-disponibles-et-limites).

Les positions et appels temporaires restent en RAM. Aucun nouveau SET Redis n’est ajouté aux mouvements ni à la présence. Comptes, personnages, amitiés et équipes rejoignent les lots de sauvegarde. Les signatures de progression sont recalculées pour les sessions modifiées ; les consultations inchangées ne rescannent plus tous les tutoriels. Les cartes de combat sont copiées par sérialisation JSON et les vues sont préparées à la demande plutôt qu’à chaque tick.

Le tick de simulation est programmé toutes les 200 ms et ignore les personnages absents depuis 60 secondes. Sur le moteur propriétaire, les états sont poussés toutes les 150 ms jusqu’à quatre présences, toutes les 500 ms jusqu’à 16 présences, puis chaque seconde. Les instances de relais restent à une seconde afin de garder une marge pour les actions. Cette fréquence ne déclenche aucune sauvegarde D1 à elle seule.

Les commandes WebSocket renvoient directement leur état actualisé en bundles, sans attendre la prochaine poussée et sans lecture réseau supplémentaire du client. Les autres joueurs peuvent attendre la diffusion périodique pour voir cette action. Le relais traite les requêtes reçues avant de publier le lot de réponses, sans augmenter la fréquence des publications Redis. Les compétences favorites restent visibles ; le maintien ouvre les choix supplémentaires et le glissement active la compétence au relâchement. Les messages et actions contextuelles sont positionnés indépendamment du bouton d’attaque.
