# Révision de qualité — objectif 90/100

Date : 8 octobre 2026. Base : `d85cbd97e7c40f96bdc44548c12872bc5befd3d7`, branche publiée `alpha-vercel-turso`.

Cette révision corrige le logiciel existant. Elle conserve les cartes, les cinq classes jouables, les quêtes, les recettes et les règles de combat. Elle ne crée aucune fonctionnalité de jeu.

## Score et portée

Le score de l'audit initial est 66/100. La grille ci-dessous décrit un **candidat à 90/100**, sous réserve de la réussite de la CI GitHub et de la vérification de la version de production. Ce n'est pas une certification du site actuellement publié, ni un score Lighthouse. Les notes sont une appréciation de qualité documentée, pas une mesure de performance.

| Axe | Audit initial | Candidat | Justification et limite |
| --- | ---: | ---: | --- |
| Fonctionnement | 16/20 | 19/20 | Repli HTTP, connexion authentifiée, déconnexion vérifiée et tests des parcours existants. Le parcours complet sur les cartes actuelles reste à confirmer dans le navigateur publié. |
| Sécurité | 10/15 | 14/15 | Authentification avant admission WebSocket, délai et nombre de connexions en attente bornés, JSON strict, HSTS et secrets CI limités aux étapes utiles. Aucun audit offensif exhaustif. |
| Sauvegarde | 8/15 | 14/15 | Renommages capturés, suppressions persistées, journal à durée limitée, reprise et fencing testés, remise à zéro interdite au démarrage Vercel, vidage à l'arrêt. La restauration d'une sauvegarde externe n'a pas été exercée. |
| Performance | 6/10 | 9/10 | Calcul scrypt hors verrou de simulation, compression des gros reçus, cache des fichiers versionnés, test local avec 40 aventures. Aucune extrapolation au débit Vercel réel. |
| Architecture et maintenance | 6/10 | 8/10 | Parseur JSON et journal isolés, validation partagée entre adaptateurs, migration additive, déploiement préparé puis vérifié avant promotion. Les grands modules et les sources historiques dupliquées subsistent. |
| Tests | 8/10 | 10/10 | Régressions ciblées, Redis réel entre deux instances, monde publié et cinq classes, interface HTTP et commandes tactiles. Les intégrations externes absentes restent ignorées. |
| Interface et accessibilité | 7/10 | 9/10 | Joystick au clavier, réduction des animations, consignes de mot de passe et texte de sauvegarde plus exacts, déconnexion sans faux succès. Tests matériels et lecteurs d'écran complets à faire. |
| Contenu et équilibre | 3/5 | 3/5 | Contenu et valeurs de combat inchangés ; aucune note ajoutée pour du contenu nouveau. |
| Métadonnées | 2/5 | 4/5 | Description, canonical, Open Graph et Twitter. Aucune illustration sociale ajoutée. |
| **Total** | **66/100** | **90/100 conditionnel** | **La production doit être vérifiée avant de confirmer cette note.** |

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
10. Toute modification de la branche publiée déclenche le workflow : les cartes, dépendances et configurations ne sont plus oubliées. Les actions du workflow de production sont épinglées, les secrets sont limités aux étapes qui en ont besoin, et la version est testée avant promotion.

## Vérifications

- Suite pytest complète avec Redis réel local : 1 476 tests réussis, 7 ignorés, 1 avertissement de dépréciation Starlette/httpx.
- Test du monde actuel : 40 comptes et aventures, cinq classes, huit cartes, deux quêtes, 80 lectures d'état puis restauration des 40 aventures.
- Mesure locale de ce scénario : p95 2,17 ms, maximum 14,48 ms. Il s'agit de lectures séquentielles d'aventures initiales dans le moteur local, **pas de 40 joueurs simultanés en combat dans Vercel**.
- Interface HTTP : parcours à deux joueurs jusqu'à Brume, social à quatre comptes, HUD, combat tactique, contrôles tactiles et administration.
- Transport : WebSocket bloqué, authentification, repli HTTP et conservation de l'identifiant lors d'une nouvelle tentative de commande.
- Migration additive et persistance via le protocole Turso simulé ; Redis réellement exécuté pour les tests de coordination. La base de production n'a pas été modifiée pendant cette préparation.

## Livraison et compatibilité

La nouvelle table `receipt_expiry` et son index sont ajoutés sans suppression de compte ou de personnage. Le stockage initialise le schéma au premier enregistrement si nécessaire. Le déploiement doit être fait depuis cette révision exacte et vérifié avant promotion.

Le workflow utilise l'environnement GitHub `production`. Pour un workflow avec secrets, la compétence Vercel impose une branche protégée avec code relu, ou l'approbation du commit exact par un reviewer requis de cet environnement. La branche actuelle était non protégée lors de la préparation ; les règles de protection n'ont pas été modifiées automatiquement.

Après publication : vérifier connexion, sélection de personnage, reprise d'aventure, une action avec perte réseau, sauvegarde après renommage et parcours mobile. Les journaux Vercel étaient inaccessibles au connecteur lors de l'audit ; aucune affirmation d'absence d'erreurs en production n'est faite.

Une ancienne version ne sait pas relire les reçus compressés : pour un retour à cette ancienne version, supprimer uniquement le journal transitoire (`receipts` et `receipt_expiry`) sous maintenance, ou attendre son expiration et le vider. Ne pas supprimer les comptes, personnages ou aventures. Les anciens checkpoints doivent être conservés jusqu'à validation de la nouvelle version.
