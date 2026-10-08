# Sécurité du POC

## Périmètre

Le POC permet un tutoriel coopératif et des duels entre joueurs dans un environnement contrôlé. Il ne constitue pas une certification de sécurité ni une infrastructure de production publique.

Le serveur HTTP local reste limité à la boucle locale. Le déploiement web utilise l’entrée FastAPI/ASGI et impose les contrôles d’hôte et d’origine. Toute exposition personnalisée doit rester sous HTTPS. Ne pas transmettre les jetons de session, mots de passe ou secrets administrateur en URL, dans un journal ou dans un canal public.

## Protections mises en place

- Identifiants de personnages et invitations générés par le serveur avec un générateur cryptographique. Les secrets d'authentification et de recherche d'invitation sont stockés sous forme de SHA-256 ; le reçu privé de création de salon contient l'invitation pour assurer sa déduplication.
- Toutes les mutations requièrent une identité authentifiée. Un joueur ne peut pas fournir l'identifiant d'un autre acteur ni une cible extérieure à son groupe ou à son combat.
- Accès aux sessions limité aux membres de la même portée. Un code d'invitation est requis pour rejoindre ; au maximum deux joueurs sont acceptés.
- Démarrage réservé au créateur, réservation unique des joueurs, délai d'attaque calculé par le serveur, fin de duel et version d'état contrôlés.
- Transactions SQLite, requêtes paramétrées, reçus persistés et contrôle des versions pour les actions concurrentes ou retransmises.
- Rejet des paramètres inconnus, JSON dupliqué/non fini, noms avec caractères de contrôle, classes non jouables, corps supérieurs à 4 Kio et hôtes/origines non autorisés.
- En-têtes CSP, refus de framing, absence de CORS, aucun secret dans les URL ou les réponses d'état. Les noms et événements sont rendus par `textContent`, sans HTML utilisateur.
- Fichier de base créé avec des permissions 0600 sur les systèmes POSIX. Les ACL du dossier restent de la responsabilité de l'administrateur sur Windows.
- Les sauvegardes JSON historiques rejettent séparateurs, points seuls et identifiants non conformes ; leurs chemins sont vérifiés, les liens symboliques ciblés sont refusés et les écritures utilisent un remplacement atomique.

## Limites explicites

Le serveur local accepte au maximum 128 traitements HTTP concurrents. Les routes appliquent des limites distinctes, notamment 10 tentatives de connexion ou créations de compte par minute et par adresse et 60 commandes par minute et par identité. Quand Redis est configuré, les limites et la présence runtime sont partagées entre instances ; sans Redis, des fallbacks locaux ou base de données sont utilisés selon le mode d’exécution. Ces garde-fous ne remplacent pas une protection réseau en amont.

Le stockage est borné à 1 000 personnages, 2 000 sessions et 100 000 reçus de commande. Une session conserve les 100 derniers événements. Les reçus ne sont pas purgés automatiquement afin de conserver la déduplication. Une limite atteinte produit un refus 429. L'administrateur peut démarrer un nouveau monde avec un autre fichier de base ; aucune suppression des données existantes n'est automatique.

Les comptes utilisent un nom d’utilisateur et un mot de passe dérivé avec scrypt. Les sessions sont des jetons révocables, avec un maximum de sessions actives conservées par compte ; le changement de mot de passe révoque les anciennes sessions et une déconnexion globale est disponible. Le POC n’inclut pas encore OAuth ni récupération de compte par email.

Les fichiers sont protégés contre les entrées du joueur, mais le POC suppose que le compte système et le répertoire de données sont de confiance. Un utilisateur local capable de modifier les fichiers du serveur ne fait pas partie du modèle de menace. En production temps réel, Redis coordonne le propriétaire du moteur, les fences de sauvegarde, la présence et le rate limiting distribué ; Turso conserve l’état durable.

La reprise compte le temps hors ligne à partir de l'horloge système UTC et empêche un retour en arrière du temps de jeu. Une modification importante de l'heure pendant l'arrêt peut faire avancer les échéances. Les durées des compétences du moteur historique restent exprimées en tours ; elles ne sont pas implicitement converties en secondes du POC.

## Signalement et vérification

Pour signaler une vulnérabilité, privilégier le signalement privé GitHub si activé, ou contacter le propriétaire du dépôt sans publier de secret exploitable.

Les tests de sécurité se trouvent dans `test/test_multiplayer.py` et `test/test_security_regressions.py`. Les tests d'intégration liés à un bot externe absent sont ignorés explicitement et ne constituent pas une validation d'un bot Discord déployé.

Le tutoriel conserve ses personnages et leurs effets dans des données JSON internes, sans pickle ni exécution de code fourni par le client. La compétence doit appartenir aux compétences acquises de la classe, la cible doit être autorisée par son type, et l'énergie et les délais sont contrôlés par le moteur. Les étapes, récompenses, recettes et coûts sont définis côté serveur. La validation d'une quête et la fabrication avec consommation des matériaux sont atomiques et dédupliquées. Les membres reçoivent chacun leur butin, mais doivent fabriquer chacun leur équipement avant de voyager. Les tutoriels sont persistants et ne sont pas soumis à l'expiration des duels.

Le filtrage des écrans et des cibles dans le navigateur n'accorde aucune permission. Le serveur vérifie de nouveau le type et l'état de la cible, l'appartenance au groupe, l'acquisition de la compétence, l'énergie, les délais et la capacité d'invocation. Un soin sur un personnage à pleine vie est refusé. L'attaque simple du tutoriel exige une cible explicite et rejette les joueurs, les cibles inconnues ou un ennemi mort. Le duel accepte une cible explicite et la vérifie ; l'ancienne commande sans cible reste compatible avec son adversaire unique.
