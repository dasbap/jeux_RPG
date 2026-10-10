# Audit et optimisation du RPG — 9 octobre 2026

## Mise à jour après accès Vercel et CI distante

La session Vercel a été ouverte avec le propriétaire. Le projet et son ID correspondent au workflow. Le domaine public sert **d85cbd9**, branche **alpha-vercel-turso** ; le build **9a5f1ea** de `prod` est **Ready / Production / Staged**, sans promotion. Vercel Authentication est active et aucun secret de bypass d'automatisation n'existe dans Vercel ni GitHub. Les secrets Vercel/Turso existants ne doivent pas être remplacés.

Tous les workflows du commit **10678839** de la [PR #28](https://github.com/dasbap/jeux_RPG/pull/28) ont réussi : Python 3.11/3.12/3.13, Redis réel, éditeur Windows, UI/Playwright/HUD, lint, installation et performance. Python 3.12 rapporte **1 563 réussis, 7 ignorés**, 86,97 s. Les exclusions locales Redis et rendu navigateur ont donc été levées par la CI, sans constituer une recette mobile réelle ni un essai Redis de production.

Le workflow contrôle maintenant la présence du secret avant build et modifications Turso. Le healthcheck diagnostique les réponses non JSON et HTTP 401/403 sans afficher le corps ou un secret, et conserve le contrôle du SHA. Huit nouveaux cas couvrent ces refus. Leurs tests ciblés passent ; la CI du nouveau commit reste à contrôler.

Les instantanés de la vue projet montrent 168 invocations, 168 requêtes CDN et 0 % d'erreurs sur six heures ; cela ne mesure pas la consommation mensuelle ni les quotas restants. Upstash est identifié par les variables liées dans Vercel, sans lecture de leurs valeurs. Les autres mesures et le score estimatif de 80/100 restent prudents.

La [configuration précise restant à effectuer](DEPLOYMENT_SETUP.md) détaille le seul nouveau secret demandé, `VERCEL_AUTOMATION_BYPASS_SECRET`, les protections de l'environnement et le chemin PR vers `prod`. Aucun déploiement, fusion, secret ou réglage de protection n'a été modifié. Les formulations d'accès bloqué et de CI à contrôler ci-dessous décrivent l'état initial de l'audit et sont remplacées, sur ces points, par cette mise à jour.

## Résultat et périmètre

Les optimisations prioritaires sont proposées dans une branche dédiée, sans migration, modification des règles de jeu ou accès en écriture aux données de production. Le résultat est **révisable, mais pas certifié en production**. Le score estimatif est **80/100**, avec confiance moyenne ; l'objectif de 90/100 n'est pas atteint avec les validations accessibles.

Référence de comparaison : `master`, commit `f27dabee1b4b886ea117debf18d9cb6322c03356`, version `0.11.0a25`. La consigne ultérieure « Utilise le dernier commit pour redéployer » définit ce commit comme cible initiale ; elle ne prouve pas le SHA actuellement servi. La branche `prod` observée pointe sur `9a5f1ea74dae35cf1f1ef6e777a90ba6c1508f18`.

- [Dépôt](https://github.com/dasbap/jeux_RPG)
- [Branche de travail et commits](https://github.com/dasbap/jeux_RPG/commits/perf/resource-stabilization-20261009)
- [Comparaison à master](https://github.com/dasbap/jeux_RPG/compare/master...perf/resource-stabilization-20261009)
- [Projet Vercel fourni](https://vercel.com/dasbaps-projects/jeux-rpg)
- [Site public inspecté](https://jeux-rpg.vercel.app/)

La dernière tentative de publication examinée, [workflow 37914369515](https://github.com/dasbap/jeux_RPG/actions/runs/37914369515), a échoué à la vérification HTTP avant promotion. Les tests, le contrôle Turso, le schéma et le build avaient passé. Le vérificateur a reçu une réponse non JSON sur `/health`. Le déploiement généré était protégé et le secret de contournement était absent ; c'est une explication plausible, pas une cause démontrée. Aucun nouveau déploiement n'a été réalisé.

Le connecteur voit l'équipe Vercel mais renvoie 404 pour le projet par son nom et son identifiant, et 403 pour ses déploiements. La CLI locale ne possède pas de connexion. Le lien du projet ne débloque pas ces droits. Les consommations réelles Vercel, Turso et Redis, les journaux de production, les sauvegardes distantes et le SHA servi restent inconnus.

## Changements réalisés

### HTTP et interface

Le polling fixe a été remplacé par un unique `setTimeout` récursif. Les protections contre les requêtes superposées et les réponses obsolètes sont conservées. Les fréquences sont recalculées après une commande, une réponse et un changement de connexion.

| Situation | Intervalle nominal de secours HTTP |
|---|---:|
| Combat actif ou déplacement | 1 s en production, 250 ms en local |
| Exploration calme | 3,6 s |
| Salon sans aventure | 5 s |
| Autre menu hors combat | 15 s |
| Onglet caché | 20 s |
| WebSocket connecté | Aucun polling périodique HTTP |
| Hors ligne, sans jeton ou sélection de personnages | Aucune lecture d'état périodique |

Un jitter de ±10 % désynchronise les clients. Les erreurs réseau déclenchent un recul exponentiel jusqu'à 30 s nominales. Le retour au premier plan, `pageshow` et le retour en ligne forcent une actualisation. Les commandes conservent leurs vérifications et leur actualisation immédiate. Le salon est limité à 5 s pour que l'arrivée d'un compagnon reste visible rapidement. Les changements reçus uniquement par polling dans un menu peuvent prendre jusqu'à environ 16,5 s hors temps réseau ; cette limite doit être évaluée lors de la recette réelle.

### WebSocket et simulation

Un délai partagé empêche les appels HTTP successifs de relancer une poignée de main WebSocket pendant le recul réseau. Les anciennes connexions ne peuvent plus injecter de réponses. La fermeture nettoie heartbeat et promesses en attente. Une déconnexion explicite ne relance pas la connexion. Le recul exponentiel atteint 30 s nominales avec jitter ±20 %.

Les GET et les commandes identifiées conservent le repli HTTP existant ; les autres mutations déjà envoyées ne sont pas rejouées automatiquement. Aucun contrôle d'authentification n'est retiré.

Un onglet caché avec une souscription WebSocket maintient désormais une lecture serveur toutes les 20 s, sans émission du payload d'état. Cela renouvelle la présence et permet à la simulation existante de continuer. Un test contrôle ce renouvellement et une modification de l'état simulé.

**Limite :** si le navigateur suspend entièrement la connexion, si le dernier socket ferme ou si le bail du propriétaire expire, cette modification ne garantit pas un monde autonome toujours actif. La garantie exigerait une décision d'hébergement ou un worker persistant ; aucun service payant n'a été ajouté.

### Présence, stockage et moteur

- Une admission lit les valeurs du registre une fois au lieu d'une fois par serveur.
- La présence est renouvelée au maximum toutes les 10 s pour une présence existante inchangée ; création et changement de serveur sont immédiats. Expiration à 60 s et capacité à 40 joueurs par serveur restent inchangées.
- Le statut social compare désormais les timestamps de présence à l'horloge murale correspondante ; la comparaison à l'horloge monotone était un bogue confirmé.
- Une capture SQLite du runtime sélectionne seulement les lignes de la session modifiée. Une liste vide de signatures ne lance plus de requête. Les sous-ensembles utilisent des paramètres SQL.
- La recherche de chemins utilise un ensemble immuable des couvertures dans son calcul interne mis en cache. Les cartes globales et les clés du cache ne changent pas. 45 cas comparés au commit de référence donnent exactement les mêmes chemins.

Ces changements réduisent des opérations du runtime local et du registre distribué. Ils ne démontrent pas une diminution chiffrée des lectures facturées Turso : le chargement distant, les transactions et le checkpoint global restent à mesurer avec les services réels.

### CI et outillage

Les workflows de tests et lint évitent le doublon push/PR sur les branches de travail ; les pushes de `master` et `prod` restent couverts. Les anciennes exécutions de tests/lint sur une même référence sont annulées. La publication n'est pas annulée automatiquement par ce changement.

La couverture lignes/branches est produite et archivée sur Python 3.12. Ruff contrôle les erreurs de syntaxe et les références invalides avec une version fixée ; ceci ne représente pas un nettoyage stylistique intégral. Les actions du workflow lint sont épinglées. Le test du polling est ajouté aux tests UI et à la préparation du déploiement.

Le banc de charge expose moyenne, p95, p99, taux d'erreur, temps CPU serveur et RSS maximale. Le test d'interface utilise un document visible et force l'actualisation après ses mutations directes hors UI. L'horloge accélérée du banc d'interface est alignée avec son ratio déclaré, afin de ne pas expirer artificiellement les flux de chat après trois secondes réelles.

## Mesures comparatives

Les résultats détaillés sont dans les fichiers JSON voisins. Les mesures de polling utilisent l'horloge simulée et le code client réel ; elles ne sont pas des statistiques Vercel. Le jitter est fixé à sa valeur médiane pour une comparaison reproductible.

| Lectures d'état sur 120 s | Avant | Après | Réduction |
|---|---:|---:|---:|
| Exploration calme | 121 | 34 | 71,9 % |
| Menu hors combat | 121 | 9 | 92,6 % |
| Salon | 121 | 25 | 79,3 % |
| Onglet caché, HTTP | 121 | 7 | 94,2 % |
| Hors ligne | 121 tentatives | 0 | 100 % |
| Combat actif | 121 | 121 | 0 %, réactivité conservée |
| WebSocket connecté | 1 | 1 | Déjà sans polling périodique |
| Erreurs réseau | 15 | 8 | 46,7 % |

La réduction des tentatives hors ligne concerne le client, pas des invocations serveur facturées. Pour un onglet caché sans WebSocket, l'ordre de grandeur devient 180 lectures d'état/h au lieu de 3 600, hors commandes, reprise et jitter. Cela ne suffit pas à prédire les invocations totales ou les heures CPU.

| Micro-banc reproductible | Avant | Après | Interprétation |
|---|---:|---:|---|
| Lectures `values()` de présence pour 100 admissions / 3 serveurs | 300 | 100 | −66,7 % de ces lectures |
| Renouvellements à instant constant sur les mêmes admissions | 100 | 1 | −99 % dans ce scénario de rafale |
| SQL signatures sur un ensemble vide | 1 | 0 | Élimination de cette lecture |
| Signature d'une session parmi 40, médiane | 0,04863 ms | 0,01828 ms | −62,4 %, SQLite local |
| CPU recherches de chemins à cache froid, médiane | 0,58763 s | 0,20219 s | −65,6 %, 45 cas identiques |

Le gain de 99 % des écritures n'est pas une projection mensuelle Redis. À une lecture/seconde par joueur, le renouvellement stable passe plutôt d'environ 60 à 6 écritures/minute. Prune, get, coordination, checkpoints et heartbeat restent présents. Les chemins ont été comparés dans le même processus à partir des fonctions exactes du commit de référence ; cela ne mesure pas tout le CPU du moteur.

### Charge locale après changement

Scénarios courts, environ cinq secondes, HTTP avec connexions persistantes, état à 1 Hz, déplacements toutes les 4 s, la moitié des joueurs en combat avec IA réelle et PV augmentés pour maintenir les combats. Chaque nombre de joueurs est un essai indépendant. SQLite local et comptes factices ; aucune charge envoyée à la production.

| Joueurs | Serveurs | p95 HTTP (ms) | CPU serveur (s) | RSS maximale (MiB) | Erreurs HTTP |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 6,99 | 0,2164 | 36,2 | 0 |
| 2 | 1 | 12,73 | 0,2236 | 36,2 | 0 |
| 10 | 1 | 30,82 | 0,8906 | 37,7 | 0 |
| 20 | 1 | 65,06 | 1,5623 | 39,7 | 0 |
| 40 | 1 | 139,68 | 2,8498 | 43,8 | 0 |
| 100 | 3 | 372,11 | 3,9584 | 56,1 | 0 |

Le premier essai à 100 joueurs sur un serveur a rencontré `server_full`, limite attendue à 40. L'essai valide utilise les trois serveurs déjà pris en charge. À 100 joueurs : 500 lectures, 100 déplacements, p99 405,71 ms, 50 combats actifs en fin d'essai. Ces essais ne constituent ni un soak test ni une certification de 100 joueurs sur Vercel. Certains travaux locaux se déroulaient en parallèle ; les latences ne doivent pas être traitées comme un benchmark matériel isolé.

Les bundles existants passent en moyenne de 19 785 octets complets à 8 421 octets différentiels dans l'essai à 100, soit 57,4 %. Ce mécanisme existait avant cette PR ; ce gain n'est pas attribué aux nouveaux changements. Aucun avant/après global CPU, mémoire ou p95 réseau de production n'est disponible.

## Tests et preuves

- Référence : **1 558 réussis, 8 ignorés**, 127,94 s.
- Après : **1 562 réussis, 8 ignorés**, 113,30 s ; un avertissement Starlette/httpx de dépréciation. L'écart de durée n'est pas présenté comme un gain de performance.
- Couverture lignes : **77,59 → 77,90 %** ; branches **70,84 → 71,38 %**. L'objectif de couverture exhaustive n'est pas atteint.
- Quatre nouveaux tests : renouvellement/capacité/expiration, statut social, simulation avec WebSocket caché, persistance isolée des sessions.
- 156 tests ciblés moteur/chemins réussis ; Ruff et vérification de syntaxe réussis.
- Vérificateurs transport, polling, conflits UI, Mira, contrôles tactiles et administration réussis localement.
- Vérification HTTP/jsdom : réussie, parcours à deux joueurs jusqu’à Brume et social à quatre comptes. Les scénarios portent sur le combat tactique, le HUD, le parcours coopératif jusqu'à Brume et le social.

Les huit exclusions sont explicites : deux modules de cartes suspendus dans le dépôt, un test Tk sans bibliothèque native, un test Redis réel faute de serveur local, quatre tests d'intégration du bot externe absent. Les tests de protocole Turso et de coordination simulée sont inclus dans pytest ; ils ne remplacent pas un essai des services distants.

Playwright/layout sur navigateur réel, recette mobile et audit complet d'accessibilité n'ont pas été exécutés dans ce poste. Les captures du HUD et le contraste ne sont donc pas certifiés. La CI conserve les vérifications Playwright existantes ; leur résultat distant doit être contrôlé après ouverture de la PR.

### Reproduction

Depuis un environnement isolé Python avec les dépendances du projet et de test :

```sh
python -m pip install -c constraints.txt '.[test]' pytest-cov==7.1.0 ruff==0.16.10
python -m pytest -q -rs --cov=jeuxRPG --cov-branch
python -m ruff check jeuxRPG
node scripts/verify_transport.cjs
node scripts/verify_polling.cjs
node scripts/verify_ui_retry.cjs
python scripts/verify_http_ui.py
python scripts/measure_resource_changes.py --baseline f27dabee1b4b886ea117debf18d9cb6322c03356 --output resources.json
```

Installer jsdom 26.1.0 dans `.ui-test`, ou configurer `NODE_PATH`. Les fichiers `polling-before.json`, `polling-after.json`, `resources.json` et `load-*.json` contiennent les mesures de cette session. Le script de comparaison des ressources requiert le commit de référence disponible localement.

## État des demandes de la mission

« Validé localement » signifie une preuve locale, sans garantie de comportement des fournisseurs distants. Aucun soupçon de sécurité n'est classé comme vulnérabilité démontrée.

| Section / tâche | Statut | Preuve ou reste à faire |
|---|---|---|
| 1–3 Contexte, objectif, protection | Appliqué | Référence exacte, branche dédiée, données factices, aucun changement distant de données |
| 4 Architecture, entrées, moteur, dépendances | Audité partiellement | Python/ASGI, JS modulaire, SQLite/Turso/Redis et CI confirmés ; refonte et typage complet différés |
| 5 Site de production | Partiel / bloqué | Accueil/login/cinq classes inspectés sans mutation ; `/health` 404 et `/api/health` 401 d'identité sur le domaine public ; SHA, compte joueur et logs inconnus |
| 6 Coûts et quotas gratuits | Partiel / bloqué | Opérations locales mesurées ; consommation et marge des comptes inaccessibles |
| 7 Polling adaptatif | Implémenté et testé | Fréquences, non-chevauchement, hors ligne, visibilité, combat, transitions, recul |
| 8 WebSocket | Corrigé partiellement | Recul partagé, repli, nettoyage, auth existante, présence cachée ; suspension totale et production à tester |
| 9 Turso, lectures/écritures, transactions, index | Partiel | Capture runtime ciblée ; protocole simulé testé ; aucun nouvel index ou changement de schéma ; facturation distante non mesurée |
| 10 Redis | Partiel | Lectures et renouvellements de présence réduits ; coordination simulée testée ; Redis réel, TTL/checkpoints distants et commandes totales à mesurer |
| 11 Moteur, IA, collisions, chemins | Optimisation ciblée validée | Couvertures internes immuables, 45 chemins identiques ; IA en charge ; pas de réécriture globale |
| 12 Couplage et responsabilités | Différé | Pas de découpage massif sans nécessité ; limites runtime/serverless documentées |
| 13 Qualité, erreurs, typage | Partiel | Ruff, syntaxe, horloges corrigées, tests ; typage complet et uniformisation des exceptions non réalisés |
| 14 Authentification et sessions | Non-régression locale | Suite existante et transport ; aucune baisse de contrôle ; secrets et sessions réelles non audités |
| 15 Commandes et concurrence | Non-régression locale | Identifiants conservés, conflits et persistance couverts ; cohérence inter-instance réelle à confirmer |
| 16 Sécurité web | Partiel | Tests existants JSON/XSS/admin et refus métier ; pas de pentest complet ni de certification des en-têtes en production |
| 17 Suite de tests | Validée localement | 1 562 réussis ; huit exclusions documentées ; CI distante à contrôler |
| 18 Couverture | Mesurée et ajoutée à CI | Lignes 77,90 %, branches 71,38 % ; zones non couvertes restent présentes |
| 19 Charge 1/2/10/20/40/100 | Essais courts réalisés | Fichiers JSON, aucune erreur sur scénarios valides ; manque test long, panne réelle, Vercel/Turso/Redis |
| 20 Fluidité, DOM et chargement | Partiel | Polling et HUD/jsdom ; protocoles de bundles/cache existants conservés ; mesures navigateur réel manquantes |
| 21 Accessibilité/mobile | Partiel | Contrôles tactiles existants vérifiés ; clavier complet, lecteur d'écran, contraste et recette appareils à faire |
| 22 Écart master/prod | Identifié, non résolu | `master` principale, publication depuis `prod`, SHAs distincts ; aucune fusion ou modification production automatique |
| 23 GitHub Actions | Amélioré | Couverture, Ruff, polling, concurrence tests, moins de doublons ; protection des branches/environnement à vérifier/configurer |
| 24 Déploiement | Bloqué | Projet inaccessible, CLI non connectée ; dernier pipeline échoué avant promotion ; aucune publication prétendue |
| 25 Livrables | Rapport, code et mesures préparés | Branche et PR de revue ; maintenance et procédure ci-dessous |
| 26 Score | Calculé, non certifié | 80/100, justification ci-dessous ; cible 90 non atteinte |
| 27 P0–P5 | Partiellement clôturé | Détail de priorité ci-dessous |
| 28 Conditions de validation | Partiellement satisfaites | Local vérifié ; déploiement, quotas, recette distante et accessibilité empêchent une validation intégrale |
| 29 Indicateurs | Mesurés sur le périmètre accessible | HTTP/présence/chemins améliorés ; CPU total, allocations, p95 et marges réelles non démontrés |

### Clôture par priorité

- **P0 :** branches/référence/mesures/tests établis ; schema inchangé et fixtures isolées. Version réellement déployée et sauvegardes de production : bloquées par accès.
- **P1 :** polling, présence, recul WS, capture SQLite et chemins : réalisés. Payload caché réduit côté WS. Chargement Turso global, checkpoint Redis global et quotas réels : ouverts.
- **P2 :** bogue d'horloge sociale et présence cachée : corrigés. Transactions, migrations existantes, commandes concurrentes et reprise : tests locaux existants conservés. Pannes réelles Redis/Turso et production : ouvertes.
- **P3 :** CI et contrôle d'erreurs renforcés. Typage intégral, découpage des grands modules et réduction générale du couplage : différés.
- **P4 :** reprise visible/en ligne et salon améliorés ; réactivité combat conservée. Recette mobile, accessibilité, contraste et rendu réel : ouverts.
- **P5 :** tests locaux, mesures, rapport et documentation : réalisés. PR de revue livrée avec le rapport. Publication vérifiée : bloquée.

## Quotas et estimation prudente

Références publiques consultées le 9 octobre 2026 : [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Turso](https://turso.tech/pricing), [Upstash Redis](https://upstash.com/pricing/redis). Elles ne prouvent ni le plan ni le fournisseur exact du compte connecté.

Vercel Hobby affiche notamment 1 million d'invocations et 4 heures de CPU actif mensuelles. Turso gratuit affiche 500 millions de lignes lues, 10 millions écrites et 5 Go de stockage. Upstash gratuit affiche 500 000 commandes mensuelles ; la page comporte des valeurs divergentes de capacité (250/256 Mo), à confirmer dans le compte. Le fournisseur Redis actif du jeu n'a pas été certifié.

Réduire le polling ne rend pas automatiquement économique une simulation continue avec un propriétaire Redis et des messages de coordination. Pour décider si les plans gratuits suffisent, mesurer séparément invocations, CPU actif, mémoire provisionnée, trafic, lignes Turso et commandes Redis pendant une journée représentative, puis extrapoler avec marge. Aucun pourcentage de quota restant n'est calculé sans compteur réel.

## Score estimatif détaillé

| Catégorie | Note / maximum | Argument, progrès et limite | Confiance |
|---|---:|---|---|
| Architecture | 12/15 | Modules existants conservés, runtime ciblé ; dépendance à un propriétaire actif et couplage restant | Moyenne |
| Qualité du code | 8/10 | Ruff ciblé, syntaxe, horloges cohérentes ; typage et style globaux incomplets | Moyenne |
| Sécurité | 12/15 | Contrôles existants maintenus et tests réussis ; audit production et pentest non disponibles | Moyenne à faible |
| Tests et fiabilité | 12/15 | 1 562 tests, nouveaux cas et couverture branches ; exclusions et services réels manquants | Élevée localement |
| Performances | 8/10 | Gains mesurés polling, présence, chemins ; absence de mesures facturées et soak test | Moyenne |
| Multijoueur et données | 8/10 | Persistance isolée et présence testées, aucune migration ; cohérence réelle et suspension réseau à confirmer | Moyenne |
| Gameplay et contenu | 9/10 | Règles et ressources inchangées, tests moteur ; recette complète réelle non certifiée | Moyenne |
| Interface et accessibilité | 3/5 | UI/jsdom et tactile ; accessibilité et mobile réel incomplets | Moyenne à faible |
| CI/CD et production | 3/5 | Contrôles renforcés ; écart branches, accès et promotion encore bloqués | Moyenne |
| Documentation | 5/5 | Référence, mesures reproductibles, limites, statut, maintenance et rollback explicités | Élevée |
| **Total** | **80/100** | **Évaluation technique indicative, pas un score certifié de production** | **Moyenne** |

L'ancien 77/100 était une estimation statique. Le passage à 80 n'est pas une mesure scientifique de trois points de qualité. Pour envisager 90 : réussir CI/Redis réel et recette distante, garantir sauvegarde/reprise, vérifier les compteurs gratuits, tester les pannes et la durée, résoudre la publication et effectuer la recette accessible/mobile.

## Préparation du déploiement et retour arrière

1. Réviser la PR, obtenir le résultat des jobs distants et vérifier le dernier `master` avant toute intégration. Aucun push direct sur `master` ou `prod` dans cette préparation.
2. Rétablir l'accès autorisé au projet Vercel et lire son SHA, ses variables par nom et ses logs sans exposer les valeurs. Contrôler les protections GitHub/environnement `production` : `master` était non protégée lors de l'inspection. Aucune protection n'a été changée automatiquement.
3. Vérifier une sauvegarde/export existant de Turso et les checkpoints Redis, avec un essai de restauration isolé. Ne pas supprimer de tables ou personnages.
4. Définir le commit exact revu à publier depuis `prod` selon le workflow existant ; traiter la réponse non JSON du healthcheck et l'accès aux déploiements protégés. Ne pas contourner la vérification du SHA pour obtenir une promotion.
5. Déployer en staging, vérifier `/health` et SHA attendu, login, sélection/reprise, action idempotente après perte réseau, deux joueurs, quête, équipement, inventaire, craft, invocation, chat, sauvegarde/reconnexion et mobile. Puis promotion uniquement après résultat satisfaisant.
6. Observer erreurs, p95 et compteurs de ressources pendant une période représentative. Conserver le déploiement précédent et ses checkpoints.

Cette PR ne change ni schéma ni format de sauvegarde. Un retour au commit de référence est donc un retour de code, sans migration inverse introduite ici. La compatibilité du rollback plus ancien évoquée dans `QUALITY_REVIEW.md` reste distincte ; ne pas revenir aveuglément à une version incapable de lire les reçus compressés existants. Toute restauration doit être répétée sur une copie isolée avant la production.

## Maintenance

- Après publication : surveiller erreurs/auth/reconnexion, health/SHA, sauvegarde/reprise et p95 ; comparer compteurs journaliers à activité comparable.
- Chaque semaine : consulter invocations/CPU/traffic Vercel, lectures/écritures Turso, commandes/mémoire Redis ; vérifier les expirations et échecs de checkpoint ; projeter la fin de mois avec marge.
- Chaque mois : exercice de restauration isolé, revue de dépendances et alertes de sécurité, couverture et scénarios peu testés, recette mobile/clavier, contrôle des droits et protections CI.
- Avant une migration ou une modification moteur : tests ciblés, checkpoint compatible, branche de revue, staging et chemin de rollback documenté.

Le reste ouvert n'est pas considéré comme terminé parce que la suite locale passe. Les limites les plus importantes sont l'accès à la production, la continuité du runtime sans socket, les compteurs gratuits réels et la validation avec les services distants.
