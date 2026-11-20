# Temps réel et sauvegardes

L’entrée Vercel est une application FastAPI. Les routes HTTP et le WebSocket `/api/ws` utilisent le même moteur transactionnel. Chaque opération recharge un snapshot D1, applique les changements dans SQLite en mémoire et valide les mutations atomiquement auprès du Worker. Si le snapshot a changé, l’instance relit l’état et retente la commande. Les reçus évitent de rejouer une mutation déjà confirmée.

Le Worker de production doit exposer `runtime_snapshot` et `commit_runtime`. La CI vérifie cette capacité et teste la lecture du snapshot avant la publication. Les variables de déploiement et la procédure de bascule sont décrites dans [VERCEL.md](VERCEL.md).

## Commandes mobiles et budget réseau

Le joystick est calculé dans le navigateur. Il regroupe les mouvements du doigt, limite les intentions de déplacement à quatre par seconde et réutilise une trajectoire déjà en cours. Une position identique ne déclenche pas une nouvelle commande dans la même direction. Le relâchement annule la trajectoire avec une seule commande. Les attaques et sorts utilisent les mêmes fonctions et le même moteur autoritaire que les déplacements ; aucun serveur distinct n'est ajouté.

Avec WebSocket, les commandes renvoient leur état actualisé. Quand un onglet est masqué, les envois de mises à jour sont espacés.

Le ciblage automatique privilégie les ennemis attaquables, change de cible lorsqu'elle devient inaccessible ou meurt, et choisit une cible propre à chaque soin ou compétence. Le ciblage est automatique par défaut, sans bouton à activer. Les décisions de ciblage sont locales et ne provoquent aucune requête supplémentaire.


## Comptes, équipes et présence

L’inscription utilise un nom de compte unique, insensible à la casse, et un mot de passe de 12 à 128 caractères. Les mots de passe sont hachés avec scrypt (N=131072, r=8, p=1), avec un sel aléatoire. Les sessions opaques expirent après 30 jours ; seuls leurs hashes sont enregistrés. Le navigateur ne présente aucune clé de connexion. Chaque compte possède au maximum un personnage par classe. La sélection d’un personnage s’applique aux sessions du compte ; chaque personnage garde son tutoriel et son inventaire. Les anciennes inscriptions par clé et le PvP sont désactivés en production.

Les demandes d’amis et les invitations d’équipe sont explicites. Une équipe sociale contient quatre comptes au maximum, même si plusieurs invitations sont acceptées simultanément. Chaque personnage voyage dans sa propre session : les déplacements, les quêtes et les salles d’un allié ne déplacent pas les autres. Le chat de groupe utilise l’équipe sociale. Les joueurs de tutoriels différents sont visibles dans la même zone et sur la même carte ; les autres personnages ne sont pas des cibles attaquables.

Social, en haut à droite, présente les alliés, leur zone, leur position et leur serveur. La carte régionale indique leurs zones. Le ralliement nécessite des alliés dans la même zone et le même serveur, en vue sortie hors combat/exploration ; chaque allié accepte ou ignore l’appel. Le bouton Rejoindre trace un trajet vers un allié arrêté. Un trajet peut être mis en attente pour être rejoint en cours de route, avec des rencontres hostiles possibles sur les chemins dangereux. La reprise du trajet est individuelle.

Le réglage Builder `rules.social.realm_capacity` vaut actuellement 40 joueurs actifs par serveur de jeu. Une présence expire après 60 secondes sans lecture d’état. Les onglets d’un même personnage réutilisent cette place. Les connexions WebSocket sont également plafonnées avec ce réglage, par instance de transport et non globalement entre instances. `RPG_RUNTIME_REALMS` accepte 1 à 3 serveurs logiques ; la publication active **1**. Ce paramètre ne fixe pas le nombre d’instances physiques : Vercel reste responsable de l’autoscaling. Ces limites configurées ne certifient pas les performances à 40 joueurs ; voir les [mesures disponibles et leurs limites](ARCHITECTURE.md#mesures-disponibles-et-limites).

La présence et les changements de jeu du moteur Vercel sont enregistrés dans D1. Les signatures de progression sont recalculées pour les sessions modifiées et les vues sont préparées à la demande.

Le moteur mono-instance exécute un tick toutes les 200 ms. Sur Vercel, les opérations font avancer la simulation à partir de l’état partagé.

Les commandes WebSocket renvoient leur état actualisé en bundles. Les autres joueurs voient les changements via la diffusion périodique. Les compétences favorites restent visibles et un maintien ouvre les choix supplémentaires.
