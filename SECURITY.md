# Sécurité du POC

## Périmètre

Le POC permet un tutoriel coopératif et des duels entre joueurs dans un environnement contrôlé. Il ne constitue pas une certification de sécurité ni une infrastructure de production publique.

Le serveur HTTP est limité à la boucle locale. Toute exposition distante doit passer par un proxy HTTPS sur la même machine. Ne pas transmettre les clés personnelles en URL, dans un journal ou dans un canal Discord public.

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

Le serveur accepte au maximum 32 traitements HTTP concurrents. Les limites en mémoire sont de 600 requêtes par minute et par adresse, 10 créations de personnages par minute et par adresse, 60 commandes par minute et par identité. Derrière un proxy local, l'adresse du proxy est commune aux utilisateurs. Ces limites sont des garde-fous de démonstration, pas une protection contre une attaque réseau distribuée.

Le stockage est borné à 1 000 personnages, 2 000 sessions et 100 000 reçus de commande. Une session conserve les 100 derniers événements. Les reçus ne sont pas purgés automatiquement afin de conserver la déduplication. Une limite atteinte produit un refus 429. L'administrateur peut démarrer un nouveau monde avec un autre fichier de base ; aucune suppression des données existantes n'est automatique.

Un possesseur de clé possède l'accès au personnage. Les clés doivent être conservées en privé. Le POC n'inclut ni OAuth, ni rotation/révocation des clés web, ni récupération de compte. La fermeture d'un onglet ne bloque pas l'identité sur le serveur.

Les fichiers sont protégés contre les entrées du joueur, mais le POC suppose que le compte système et le répertoire de données sont de confiance. Un utilisateur local capable de modifier les fichiers du serveur ne fait pas partie du modèle de menace. Utiliser un seul processus applicatif propriétaire du monde pour le déploiement du POC ; SQLite protège aussi les transactions concurrentes, mais le rate limiting et les instances d'horloge restent locaux au processus.

La reprise compte le temps hors ligne à partir de l'horloge système UTC et empêche un retour en arrière du temps de jeu. Une modification importante de l'heure pendant l'arrêt peut faire avancer les échéances. Les durées des compétences du moteur historique restent exprimées en tours ; elles ne sont pas implicitement converties en secondes du POC.

## Signalement et vérification

Pour signaler une vulnérabilité, privilégier le signalement privé GitHub si activé, ou contacter le propriétaire du dépôt sans publier de secret exploitable.

Les tests de sécurité se trouvent dans `test/test_multiplayer.py` et `test/test_security_regressions.py`. Les tests d'intégration liés à un bot externe absent sont ignorés explicitement et ne constituent pas une validation d'un bot Discord déployé.

Le tutoriel conserve ses personnages et leurs effets dans des données JSON internes, sans pickle ni exécution de code fourni par le client. La compétence doit appartenir aux compétences acquises de la classe, la cible doit être autorisée par son type, et l'énergie et les délais sont contrôlés par le moteur. Les étapes, récompenses, recettes et coûts sont définis côté serveur. La validation d'une quête et la fabrication avec consommation des matériaux sont atomiques et dédupliquées. Les membres reçoivent chacun leur butin, mais doivent fabriquer chacun leur équipement avant de voyager. Les tutoriels sont persistants et ne sont pas soumis à l'expiration des duels.
