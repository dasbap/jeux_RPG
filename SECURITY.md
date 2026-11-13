# Sécurité du jeu et de ses modes d’exécution

## Périmètre

Le projet comporte un serveur HTTP local, un solo hors ligne et un multijoueur public FastAPI/ASGI sur Vercel. La production utilise Cloudflare D1 pour les données durables et Redis pour la coordination ; le PvP y est désactivé. Le mode coopératif historique à deux et les duels restent des cas de compatibilité distincts. Cette description ne constitue pas une certification de sécurité. Voir [l’architecture actuelle](docs/ARCHITECTURE.md).

Le serveur HTTP local reste limité à la boucle locale. Le déploiement web utilise l’entrée FastAPI/ASGI et impose les contrôles d’hôte et d’origine. Toute exposition personnalisée doit rester sous HTTPS. Ne pas transmettre les jetons de session, mots de passe ou secrets administrateur en URL, dans un journal ou dans un canal public.

## Protections mises en place

- Identifiants de personnages et invitations générés par le serveur avec un générateur cryptographique. Les secrets d'authentification et de recherche d'invitation sont stockés sous forme de SHA-256 ; le reçu privé de création de salon contient l'invitation pour assurer sa déduplication.
- Toutes les mutations requièrent une identité authentifiée. Un joueur ne peut pas fournir l'identifiant d'un autre acteur ni une cible extérieure à son groupe ou à son combat.
- Accès aux sessions limité aux membres de la même portée. Le salon coopératif historique exige une invitation et accepte deux joueurs. En production, une équipe sociale peut réunir quatre comptes, avec des sessions d’aventure distinctes ; ce n’est pas un accès libre à la partie d’un autre personnage.
- Démarrage réservé au créateur, réservation unique des joueurs, délai d'attaque calculé par le serveur, fin de duel et version d'état contrôlés.
- Transactions SQLite, requêtes paramétrées, reçus persistés et contrôle des versions pour les actions concurrentes ou retransmises.
- Rejet des paramètres inconnus, JSON dupliqué/non fini, noms avec caractères de contrôle, classes non jouables, corps supérieurs à 4 Kio et hôtes/origines non autorisés.
- En-têtes CSP, refus de framing, absence de CORS, aucun secret dans les URL ou les réponses d'état. Les noms et événements sont rendus par `textContent`, sans HTML utilisateur.
- Fichier de base créé avec des permissions 0600 sur les systèmes POSIX. Les ACL du dossier restent de la responsabilité de l'administrateur sur Windows.
- Les sauvegardes JSON historiques rejettent séparateurs, points seuls et identifiants non conformes ; leurs chemins sont vérifiés, les liens symboliques ciblés sont refusés et les écritures utilisent un remplacement atomique.

## Limites explicites

Le serveur local borne les traitements HTTP concurrents. Les routes appliquent des limites distinctes aux connexions, créations de compte et commandes ; le transport WebSocket borne également les messages et les authentifications simultanées. Redis permet le rate limiting distribué en production. La présence de jeu reste en RAM dans le moteur autoritaire. Les limites exactes dépendent de la route et du mode d’exécution ; elles ne remplacent pas une protection réseau en amont.

Le service conserve des bornes de stockage et un journal de commandes dédupliquées. Les reçus ont une rétention de 15 minutes et sont purgés par `command_journal.py` : l’ancien plafond cumulatif de 100 000 reçus n’est plus une limite permanente de fonctionnement. Les événements sont bornés par session. La publication et l’administration ne doivent pas supprimer les comptes ni remplacer une base existante pour contourner une limite.

Les comptes utilisent un nom d’utilisateur et un mot de passe dérivé avec scrypt. Les sessions sont des jetons révocables, avec un maximum de sessions actives conservées par compte ; le changement de mot de passe révoque les anciennes sessions et une déconnexion globale est disponible. Le POC n’inclut pas encore OAuth ni récupération de compte par email.

Les fichiers sont protégés contre les entrées du joueur, mais le compte système et le répertoire de données restent dans le périmètre de confiance. Redis coordonne le propriétaire du moteur, les générations de sauvegarde et le rate limiting distribué ; les parties et la présence sont simulées en RAM. Cloudflare D1 conserve les comptes et la progression durable via un Worker privé authentifié. Les lots atomiques et les triggers de génération refusent les sauvegardes d’un moteur périmé. Turso reste un ancien backend verrouillé, sans retour automatique en cas de panne D1.

La reprise compte le temps hors ligne à partir de l'horloge système UTC et empêche un retour en arrière du temps de jeu. Une modification importante de l'heure pendant l'arrêt peut faire avancer les échéances. Les durées des compétences du moteur historique restent exprimées en tours ; elles ne sont pas implicitement converties en secondes du POC.

## Signalement et vérification

Pour signaler une vulnérabilité, privilégier le signalement privé GitHub si activé, ou contacter le propriétaire du dépôt sans publier de secret exploitable.

Les tests de sécurité se trouvent dans `test/test_multiplayer.py` et `test/test_security_regressions.py`. Les tests d'intégration liés à un bot externe absent sont ignorés explicitement et ne constituent pas une validation d'un bot Discord déployé.

Le tutoriel conserve ses personnages et leurs effets dans des données JSON internes, sans pickle ni exécution de code fourni par le client. La compétence doit appartenir aux compétences acquises de la classe, la cible doit être autorisée par son type, et l'énergie et les délais sont contrôlés par le moteur. Les étapes, récompenses, recettes et coûts sont définis côté serveur. La validation d'une quête et la fabrication avec consommation des matériaux sont atomiques et dédupliquées. Les membres reçoivent chacun leur butin, et les conditions de quêtes et d’atelier sont vérifiées côté serveur. Le contenu de production garde l’exploration libre ; les prérequis de quêtes et l’accès à une forge sont définis dans le Builder. L’obligation de fabriquer avant Brume concerne le tutoriel de référence historique. Les tutoriels sont persistants et ne sont pas soumis à l'expiration des duels.

Le filtrage des écrans et des cibles dans le navigateur n'accorde aucune permission. Le serveur vérifie de nouveau le type et l'état de la cible, l'appartenance au groupe, l'acquisition de la compétence, l'énergie, les délais et la capacité d'invocation. Un soin sur un personnage à pleine vie est refusé. L'attaque simple du tutoriel exige une cible explicite et rejette les joueurs, les cibles inconnues ou un ennemi mort. Le duel accepte une cible explicite et la vérifie ; l'ancienne commande sans cible reste compatible avec son adversaire unique.
