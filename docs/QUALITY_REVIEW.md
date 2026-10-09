# Révision de qualité

Date : 8 octobre 2026. Intégration des PR #16 et #17 sur `master`, version `0.11.0a25`. Branche de publication : `deploy/production`.

Cette révision corrige le logiciel existant. Elle conserve les cartes, les cinq classes jouables, les quêtes, les recettes et les règles de combat. Elle ne crée aucune fonctionnalité de jeu.


## Corrections principales

1. En production, un WebSocket doit fournir un jeton de compte valide dans son premier message. Les connexions anonymes ne consomment plus les 40 places authentifiées. Les demandes d'authentification ont un délai de 10 secondes et une limite de 16 connexions simultanées par instance. Les requêtes suivantes doivent conserver le même jeton.
2. Les opérations de compte passent par HTTP. Lorsque WebSocket ne peut pas s'ouvrir, l'interface utilise HTTP et reprend les actualisations. Après une interruption, seuls les GET et les commandes munies de leur identifiant existant sont rejoués automatiquement. Une mutation sociale déjà envoyée n'est pas répétée silencieusement.
3. Le journal déduplique les commandes pendant 15 minutes et expire les anciens reçus. Les réponses volumineuses sont compressées ; les anciens reçus JSON restent lisibles. La limite cumulative de 100 000 commandes ne bloque plus tous les joueurs.
4. Les suppressions de reçus et de sessions de connexion deviennent des modifications persistées, y compris dans les checkpoints Redis. L'acquittement d'une suppression ne supprime pas une modification ultérieure.
5. Le nom d'un personnage fait partie de la signature de progression. Une intervention de l'administrateur est sauvegardée dans l'aventure.
6. Le chargement Vercel ne peut plus lancer la remise à zéro des anciens joueurs, même si l'ancien drapeau est encore présent. Le déploiement remplace ce drapeau par `0`.
7. Deux calculs scrypt au maximum peuvent être préparés simultanément, hors du verrou du moteur. Le service valide encore le compte et le hash attendu dans sa transaction avant de créer la session.
8. JSON invalide, clés dupliquées, constantes non standard et tableaux au premier niveau sont refusés avant d'accéder au moteur ASGI.
9. Les fichiers JS/CSS sont versionnés par contenu dans les pages et peuvent être conservés en cache. Les autres URLs se revalident avec ETag. Les données de compte et de jeu restent sans cache public.
10. Le workflow se lance manuellement uniquement depuis `deploy/production`. Les actions du workflow de production sont épinglées, les secrets sont limités aux étapes qui en ont besoin, et la version est testée avant promotion.

## Vérifications

- Suite pytest finale de l’intégration avec Redis réel local : 1 556 tests réussis, 7 ignorés, 1 avertissement de dépréciation Starlette/httpx.
- Test du monde actuel : 40 comptes et aventures, cinq classes, huit cartes, deux quêtes, 80 lectures d'état puis restauration des 40 aventures.
- Mesure locale de ce scénario : p95 2,17 ms, maximum 14,48 ms. Il s'agit de lectures séquentielles d'aventures initiales dans le moteur local, **pas de 40 joueurs simultanés en combat dans Vercel**.
- Interface HTTP : parcours à deux joueurs jusqu'à Brume, social à quatre comptes, HUD, combat tactique, contrôles tactiles et administration.
- Transport : WebSocket bloqué, authentification, repli HTTP et conservation de l'identifiant lors d'une nouvelle tentative de commande.
- Migration additive et persistance via le protocole Turso simulé ; Redis réellement exécuté pour les tests de coordination. La base de production n'a pas été modifiée pendant cette préparation.

## Livraison et compatibilité

La nouvelle table `receipt_expiry` et son index sont ajoutés sans suppression de compte ou de personnage. Le stockage initialise le schéma au premier enregistrement si nécessaire. Le déploiement doit être fait depuis cette révision exacte et vérifié avant promotion.

Le workflow utilise l'environnement GitHub `production`. Pour un workflow avec secrets, la compétence Vercel impose une branche protégée avec code relu, ou l'approbation du commit exact par un reviewer requis de cet environnement. La branche `master` était non protégée lors de la préparation ; les règles de protection n'ont pas été modifiées automatiquement.

Après publication : vérifier connexion, sélection de personnage, reprise d'aventure, une action avec perte réseau, sauvegarde après renommage et parcours mobile. Les journaux Vercel étaient inaccessibles au connecteur lors de l'audit ; aucune affirmation d'absence d'erreurs en production n'est faite.

Une ancienne version ne sait pas relire les reçus compressés : pour un retour à cette ancienne version, supprimer uniquement le journal transitoire (`receipts` et `receipt_expiry`) sous maintenance, ou attendre son expiration et le vider. Ne pas supprimer les comptes, personnages ou aventures. Les anciens checkpoints doivent être conservés jusqu'à validation de la nouvelle version.

## Corrections de l’intégration

Les commandes tactiques obsolètes sans identifiant de combat sont refusées avant mutation. Une action retardée munie du bon identifiant reste revalidée sur le serveur. Le relais Redis lance les requêtes dans des tâches bornées afin de ne pas attendre le hachage d’un mot de passe avant de répondre aux autres joueurs. Les écritures du moteur restent sérialisées et les identifiants relayés dédupliqués.

La capture des reçus utilise un journal de clés modifiées par des triggers temporaires ; elle ne relit plus la totalité des deux tables à chaque rafraîchissement. Les checkpoints historiques sans expiration restent relisibles. Les métriques de présence utilisent la même horloge murale que le registre. Les corrections de déconnexion et de rafraîchissement HTTP sont portées dans le client modulaire de master.

Le vérificateur de déploiement utilise l’URL générée et exige le SHA attendu dans `/health`. Un échec empêche la promotion. Les 40 commandes concurrentes dans 40 combats locaux, réparties sur les cinq classes, sont restaurées depuis un checkpoint puis rejouées avec le même résultat. Mesure de préparation : p95 278,95 ms, maximum 291,42 ms, incluant l’attente du verrou ; ce résultat ne mesure pas le réseau ou Vercel.

