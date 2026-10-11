# Audit final du RPG — 11 octobre 2026

> Rapport historique : les états de protection et de publication sont remplacés par [le suivi courant](../audit-20261011-followup/REPORT.md). Les mesures ci-dessous gardent leur date et leur périmètre.

Le dépôt a été réaudité, les défauts démontrés corrigés et les vérifications accessibles exécutées. L’audit distingue les preuves locales, les preuves CI et les observations de production. Les contrôles nécessitant les comptes fournisseurs restent explicitement ouverts. La cible de 90/100 n’est pas déclarée atteinte : l’évaluation argumentée est **85/100**, indicative et non certifiée.

Le propriétaire a autorisé la fusion lorsque tous les tests sont verts, puis demandé de reporter la sécurisation de `prod`. Les corrections de cette clôture passent par la [PR #34](https://github.com/dasbap/jeux_RPG/pull/34) vers `master`. **Aucun nouveau déploiement de ces corrections n’est lancé tant que cette étape de sécurisation est reportée.** La production existante reste la version `82a7461613ec748014d3cf5a97bdade88f1d1ee3`.

## Références et limites des preuves

- Référence initiale : `f27dabee1b4b886ea117debf18d9cb6322c03356`.
- Optimisations intégrées : [PR #28](https://github.com/dasbap/jeux_RPG/pull/28), puis [PR #31](https://github.com/dasbap/jeux_RPG/pull/31) vers `prod`.
- Correction du healthcheck ASGI : [PR #32](https://github.com/dasbap/jeux_RPG/pull/32) vers `prod` et [PR #33](https://github.com/dasbap/jeux_RPG/pull/33) vers `master`.
- Référence de cette clôture sur `master` : `cf3730d6019c342b5e3ddebe8b56532a8eff3208` ; branche de revue : `audit/final-validation-20261011`.
- Dernière preuve CI du code fonctionnel avant les finitions documentaires : `f0447bc5d7ab8528f4ebdfe5bbb5d4d5d52f1905`. Les résultats du dernier commit de la PR doivent aussi être verts avant fusion.
- Le [rapport du 9 octobre](../audit-20261009/REPORT.md) et ses JSON restent des preuves historiques, avec leur périmètre et leur date. Ses anciennes conclusions d’accès et de déploiement sont remplacées par ce rapport.

Les charges utilisent des comptes factices et SQLite local. Aucun reset, aucune suppression de personnage, aucune migration destructive, aucun changement du format de sauvegarde ou des règles de combat n’est introduit par cette clôture. Le contrôle de restauration ne touche jamais la base de production. Aucun token fournisseur n’est inclus dans les livrables.

## Défauts démontrés et corrections

| Défaut | Gravité | Cause et fichiers | Correction et preuve |
|---|---|---|---|
| Libération du propriétaire Redis interrompue par un timeout | Haute, fiabilité | Trace Vercel du 11 octobre à 01:57:25, heure de Paris : fermeture WebSocket → `Coordinator.release()` → Lua Redis → `TimeoutError` ; `multiplayer/realtime.py` | Attraper `RedisError`, conserver le store et permettre une nouvelle tentative ; avertissement sans URL ni secret ; test du timeout puis reprise |
| Fermeture du store malgré des changements non sauvegardés | Haute, données | `release()` doit tenir compte d’un flush échoué et de mutations arrivées pendant la fermeture | Vérifier `store.pending` sous le verrou ; garder le store tant que des changements restent à sauvegarder ; test de flush échoué |
| Commande simultanée à la libération | Haute, concurrence | Le store et le bail doivent changer atomiquement du point de vue des commandes | Libération Redis sous le verrou partagé ; une commande attend, puis reçoit 503 si le propriétaire a fermé ; test asynchrone explicite |
| Limite du calcul coûteux des mots de passe réinitialisée avec le store mémoire | Haute, consommation et sécurité | Limiteur en table runtime non conservée dans le checkpoint ; calcul scrypt précédant la limite de la route ; `realtime.py` | Limiteur indépendant du store, partagé via Redis quand configuré, admission avant calcul scrypt dans un thread ; 11e tentative refusée après 10 admissions malgré le remplacement du store |
| `/health` absent de l’entrée ASGI | Haute, publication | Le serveur local possédait une route que l’entrée Vercel n’exposait pas | Corrigé dans PR #32/#33 ; deux tests ; publication exacte vérifiée, puis promotion réussie |
| Vérificateur de chat envoyant des messages plus vite que le cooldown autorisé | Moyenne, fiabilité des tests | Deux canaux envoyés dans la même seconde ; `scripts/verify_ui.cjs` | Respecter le délai de saisie de 1,1 s entre les envois ; aucune réduction de la limite serveur |
| Contraste évalué pendant une animation d’apparition | Moyenne, preuve d’accessibilité | `#zone-level` analysé avant la fin de son animation ; `verify_hud_layout.cjs` | Attendre les animations avant l’analyse axe ; trois vues sans violation, deux contrôles encore incomplets |
| Actions CI encore référencées par des tags mutables | Moyenne, chaîne de dépendances | Workflows package, performance, démo et stockage | Épingler leurs actions aux SHAs déjà employés dans la CI ; éviter aussi les doublons push/PR pour package et performance |
| Neuf modules JavaScript chargés sans version de contenu | Moyenne, performance | Le HTML ne versionnait que certains assets ; neuf modules forçaient une revalidation à chaque reprise | Étendre le hash de contenu à tous les JS/CSS déclarés ; test de chaque ressource, contenu inchangé, version obsolète sans cache immutable |
| README décrivant un ancien polling fixe et l’absence de comptes | Faible, exploitation | Documentation devenue incohérente avec le code | Documenter comptes, polling adaptatif, limite du runtime serverless et contrôle de restauration |

Les quatre tests de panne/admission sont dans `test/test_realtime_failures.py`. La restauration est couverte par `test/test_backup_verification.py`. Une trace de production démontre le timeout de libération ; les autres scénarios de panne sont des tests isolés, pas des incidents de production affirmés.

## Architecture, complexité et profilage

Les entrées sont `main.py`/CLI pour le serveur local, `app.py` et `multiplayer/realtime.py` pour ASGI/Vercel, et les outils d’administration pour Turso. Le service assemble déjà des responsabilités extraites : comptes, social, commandes, tutoriel, forge, combat, présence et persistance. Le frontend est constitué de modules JavaScript natifs ; il n’a pas de chaîne de dépendances npm dans le navigateur. SQLite porte les transactions locales, Redis la coordination et les checkpoints runtime, Turso la persistance durable.

L’inventaire AST couvre **154 modules Python**. Les principaux candidats à une extraction progressive sont `realtime.create_app` (220 lignes), `map_assets.validate` (170), `tactics.advance` (168) et `server._dispatch` (155). Les points de décision syntaxiques sont enregistrés dans `architecture.json` ; ils ne constituent pas un calcul complet de complexité cyclomatique. Les imports, exceptions, états globaux, validations et frontières de concurrence ont été examinés ; aucun résultat n’est présenté comme une garantie formelle d’absence de cycle ou de duplication.

Une refonte globale, le typage intégral et la réécriture de l’IA seraient disproportionnés sans nouvelle preuve. Les interfaces, validations autoritaires et schémas restent conservés. La réduction ciblée du couplage est réalisée dans le limiteur de mots de passe, dont la durée de vie ne dépend plus du store.

Le profil courant utilise cProfile sur les tests multijoueur, tutoriel, tactique et runtime : **247 réussis, un Redis local ignoré**. `engine-profile.json` conserve les appels, temps propres et temps cumulés. Ces temps se recouvrent et incluent l’instrumentation ; ce ne sont pas des latences de production.

| Chemin demandé | Fonctions effectivement profilées |
|---|---|
| Personnage et aventure | `tutorial.unpack`, `service._session`, `new_party` |
| Initialisation de combat | `tutorial.spawn`, `tactics.begin` |
| Attaque et compétences | `tutorial.execute_one`, `tactics.execute`, `Skill.execute`, `complete_casts` |
| Déplacement et chemins | `tactics.execute`, `path`, `cached_path`, `valid_step` |
| Ligne de vue | `tactics.sight`, `sees` |
| IA et simulation | `tactics.advance`, `tutorial.advance`, `service.tick` |
| Sauvegarde et checkpoint | `RuntimeStore.persist`, `Coordinator.save`, `snapshot` ; persistance Turso simulée |
| Actualisation d’un joueur | `service.state`, `tutorial.view` |

Les coûts cumulés dominants de ce corpus concernent `state`, la reconstruction des personnages et les chemins. Le profil d’import historique avait également identifié la validation des cartes et ses chemins à froid. Cela justifie les optimisations de cache et de chemins déjà apportées, mais ne justifie pas la suppression des validations au démarrage.

## Tests, sécurité et données

La CI fonctionnelle du commit `f0447bc5` est entièrement verte : Python 3.11/3.12/3.13, Redis réel, éditeur Windows, interface, lint, paquet et performance. [Run des tests](https://github.com/dasbap/jeux_RPG/actions/runs/38097908024) : Python 3.12 annonce **1 586 réussis, 7 ignorés, un avertissement**, en 126,69 s. Ce temps n’est pas présenté comme un gain de performance. La suite locale complète du périmètre fonctionnel `f0447bc5` termine avec le code de sortie 0 ; sa couverture mesurée, avant l’extension du cache statique, est **77,76 % des lignes et 70,95 % des branches**. Le total combiné de coverage est une autre métrique et n’est pas utilisé comme couverture des lignes.

Les exclusions sont deux modules de carte suspendus, quatre intégrations du bot externe absent et une bibliothèque Tk manquante sous Linux. Localement, le test Redis ajoute une huitième exclusion ; il passe dans la CI avec Redis réel. L’avertissement de compatibilité Starlette/httpx est conservé comme dette de dépendances de test.

Le périmètre vérifié comprend authentification, expiration/révocation des sessions, changement de mot de passe, suspension administrative, propriété des personnages, invitations, actions simultanées, commandes dédupliquées, combat périmé, cooldowns, ressources, récompenses, invocations et quête/forge. Les tests de reprise couvrent les reçus persistés et les sauvegardes antérieures. Le test Redis à deux instances vérifie un propriétaire unique, un checkpoint repris par un nouveau propriétaire, une fence croissante et le refus de l’ancien propriétaire. Turso est simulé dans ce test : il ne certifie pas une panne combinée des deux services distants.

Les contrôles web portent sur JSON malformé/dupliqué, taille des corps, origine et hôte HTTP/WebSocket, injection de texte, SQL paramétré, accès admin anonyme et réponses d’erreur. Les réponses API/health de production servent `no-store` ; les en-têtes de sécurité comprennent CSP, `nosniff`, `DENY`, HSTS et `no-referrer`. Les tokens sont transmis par authentification, pas par URL ; le rendu utilisateur passe par `textContent`. Aucun pentest exhaustif n’est revendiqué.

`pip-audit` ne trouve aucune vulnérabilité connue dans les **29 dépendances publiées** inspectées ; le paquet local n’a pas d’advisory PyPI et est exclu explicitement. `npm audit` ne trouve aucune vulnérabilité connue dans les deux environnements d’outillage UI/navigateur. Ces inventaires datés sont joints ; les dépendances d’autres environnements et les vulnérabilités non encore publiées ne sont pas certifiées.

### Restauration et panne

`scripts/verify_backup.py` ouvre une source SQLite stable en lecture seule, utilise l’API de sauvegarde SQLite, contrôle intégrité et relations, compare chaque table, ouvre le moteur sur la copie puis vérifie que la source n’a pas changé. Le test crée une aventure factice, confirme sa copie et sa reprise et compare les octets de la source. La copie temporaire est supprimée à la fin du contrôle : **cet outil n’est pas une sauvegarde durable**.

Pour l’utiliser sur un export : arrêter les écritures sur cet export, conserver séparément le fichier original et exécuter `python scripts/verify_backup.py export.sqlite3`. La mémoire nécessaire à la comparaison augmente avec la taille des tables. Aucun export Turso de production n’a été fourni ou récupéré ; les politiques de sauvegarde, rétention, chiffrement et reprise fournisseurs restent à vérifier dans leurs comptes.

Une mutation en mémoire peut rester en attente avant la sauvegarde durable. Le code conserve ces changements en cas d’échec et les réessaie ; les fences empêchent un propriétaire ancien de persister. Une interruption brutale du processus avant un checkpoint durable reste un risque. La disponibilité Redis et un propriétaire actif restent nécessaires au fonctionnement distribué. Le fallback local du rate limiter pendant une panne Redis ne constitue pas une limite globale entre plusieurs instances.

## Performance et consommation

Les comparaisons historiques reproductibles sont conservées dans `audit-20261009` : sur 120 s, exploration **121 → 34** lectures d’état, menu **121 → 9**, onglet caché **121 → 7**, combat **121 → 121**, socket connecté sans polling périodique. Il s’agit d’une horloge simulée avec jitter médian, pas du compteur Vercel. La présence passe de 300 à 100 lectures `values()` pour 100 admissions et trois serveurs ; 45 chemins comparés sont identiques, avec une réduction mesurée du CPU à cache froid de 65,6 % dans ce micro-banc.

Les essais historiques courts à 1/2/10/20/40/100 joueurs sont documentés avec leurs conditions et leur révision. Cent joueurs utilisent trois serveurs ; le plafond de 40 joueurs par serveur est préservé. Ils ne certifient pas cent joueurs simultanés sur Vercel. Aucun avant/après global de CPU, mémoire ou coût de production n’est inventé.

Le nouveau test prolongé porte sur **40 joueurs pendant 180 s**, dont 20 combats indépendants avec IA réelle et PV de fixture augmentés pour maintenir le combat. Il utilise un processus serveur séparé, SQLite local, des connexions HTTP persistantes, un polling fixe à 1 Hz et des déplacements toutes les quatre secondes. Ce polling est volontairement plus exigeant que le client adaptatif calme. Les mesures finales sont dans `load-40-180s.json` : **7 200 lectures, 900 déplacements, zéro erreur ; moyenne 76,06 ms, p50 56,72 ms, p95 206,01 ms, p99 322,08 ms, maximum 569,38 ms ; CPU serveur 143,71 s, RSS maximale 67,83 MiB**. Le p95 respecte 500 ms, ce qui ne signifie pas que chaque requête le respecte. Le serveur et son ticker restent actifs, avec 20 combats à la fin. Les messages moyens passent de 49 255 octets complets à 37 489 octets différentiels (23,9 %) grâce au protocole préexistant ; ce gain n’est pas attribué aux dernières corrections. L’hôte est partagé avec d’autres vérifications : ce n’est pas un benchmark matériel isolé, ni un soak de 24 heures.

Les latences réseau des fournisseurs, leurs allers-retours facturés, les messages Redis Pub/Sub, les commandes Lua totales, le coût des transactions Turso et la récupération après panne réelle ne sont pas disponibles. Les statistiques locales de présence ne remplacent pas ces métriques. Un chargement initial Turso et un checkpoint Redis globaux restent des coûts possibles ; aucun nouvel index n’est ajouté sans requête lente démontrée.

### Compteurs Vercel effectivement consultés

Projet `jeux-rpg`, équipe `dasbaps-projects`, plan affiché Hobby. Période affichée « Last 30 Days », **10 septembre 18:00 → 10 octobre 18:00**, données pouvant avoir une heure de retard. Cette période précède la dernière publication : ces chiffres **ne mesurent pas le gain des corrections publiées** et ne correspondent pas nécessairement à une période de facturation complète. Les limites sont celles affichées dans le compte ; les autres projets de l’équipe peuvent aussi consommer les plafonds partagés.

| Compteur | Consommation affichée | Limite affichée | Marge arithmétique sur cette vue | Risque / limite |
|---|---:|---:|---:|---|
| CPU actif Fluid | 2 h 14 min | 4 h | 1 h 46 min ; 44,2 % | 55,8 % déjà affichés ; premier point de vigilance |
| Mémoire provisionnée Fluid | 39,2 GB-h | 360 GB-h | 320,8 GB-h | Ce n’est pas la RSS instantanée |
| Invocations | 2 041 | 1 000 000 | 997 959 | Faible volume ne garantit pas un faible CPU |
| Requêtes CDN | 2 061 | 1 000 000 | 997 939 | Hors projection de trafic futur |
| Fast Data Transfer | 93,32 MB | 100 GB | Environ 99,907 GB | Conversion décimale indicative |
| Fast Origin Transfer | 93,75 MB | 10 GB | Environ 9,906 GB | Conversion décimale indicative |
| Turso : lectures, écritures, taille, latence et sauvegardes | Inconnues | Non certifiées dans le compte | Non calculée | Accès aux métriques et export nécessaires |
| Upstash : commandes, mémoire, connexions, Pub/Sub et TTL | « No data available yet » dans Vercel | Non certifiées dans le compte fournisseur | Non calculée | L’intégration ne fournit pas les compteurs du fournisseur |

Aucune conclusion « le gratuit suffit » n’est établie. Une journée représentative doit mesurer séparément CPU, invocations, trafic, lignes Turso et commandes Redis, puis extrapoler avec marge. Il faut aussi vérifier la périodicité exacte et les compteurs de l’équipe.

## Interface, accessibilité et production

Les vérificateurs portent sur ciblage tactique, focus et boutons stables après 40 actualisations, appui long, déplacement, Mira, forge, chat, cartes et administration. Le scénario HTTP/jsdom utilise deux joueurs et le scénario social plusieurs comptes. La CI exécute Chromium aux tailles **1440×900**, **390×844** et **844×390** ; le HUD, les panneaux et la lisibilité y passent.

Avec axe-core 4.10.3 et les règles WCAG 2 A/AA et 2.1 AA, **aucune violation** n’est rapportée sur ces trois vues testées. `aria-prohibited-attr` et `color-contrast` restent des contrôles incomplets qui nécessitent un examen manuel. Le test attend la fin de l’animation de zone pour éviter une mesure de contraste pendant sa transparence transitoire. La navigation clavier des contrôles testés et leur focus sont couverts, mais pas la totalité du jeu au lecteur d’écran. Les tailles tactiles et la préférence de réduction des animations sont inspectées/testées dans les vérificateurs existants ; une recette sur appareils et technologies d’assistance réels reste ouverte.

Le déploiement de PR #32 a réussi dans le [run de publication](https://github.com/dasbap/jeux_RPG/actions/runs/38096554529) : tests, build, intégrité Turso, contrôle du SHA, routes, accès admin anonyme refusé, création/reprise factice, authentification WebSocket, tutoriel et vidage des changements en attente, puis promotion. Le domaine public [jeux-rpg.vercel.app](https://jeux-rpg.vercel.app/) sert le SHA `82a746…`. Une lecture d’état du runtime a été vérifiée sans aller-retour Turso ; cela ne signifie pas qu’une commande ou une sauvegarde n’en réalise jamais.

Le relevé des logs a identifié un timeout Redis de libération. Les corrections de PR #34 ne sont pas encore servies en production. Le nombre d’erreurs avant correction ne peut donc pas être transformé en preuve d’une production sans erreur après correction. Les ressources publiques et leurs en-têtes sont relevés par GET unique, sans mutation : **227 619 octets** pour le document et ses 14 assets. Le document HTML impose une revalidation ; les assets déjà versionnés sont immutable. Neuf modules JS non versionnés imposaient une revalidation ; PR #34 complète leur versionnage. Les durées observées de 3,69 à 6,88 s incluent ce client et son chemin réseau, sans avant/après ; elles ne sont pas des Web Vitals ni une certification de démarrage à froid. Connexion lente réelle, heap navigateur sur longue durée, panne fournisseur et recette complète de gameplay restent non certifiées.

## État des 29 sections de la mission

« Audité » signifie que le périmètre a été examiné et ses résultats documentés ; il ne signifie pas que chaque réserve externe est levée.

| Section | État final | Preuve ou limite précise |
|---|---|---|
| 1 Contexte | Audité | Dépôt, moteur, branche et projet existants identifiés |
| 2 Objectif | Évalué | Optimisations concrètes et score 85 ; cible 90 non certifiée |
| 3 Règles de protection | Appliquées | Fixtures isolées, PR, schémas préservés, aucune charge sur la production |
| 4 Dépôt | Audité | Entrées, architecture, 154 modules, dépendances, profil et dette documentés |
| 5 Production | Audité avec réserves | SHA, health, routes, headers, publication et logs ; slow network et heap longs manquants |
| 6 Consommation | Partiel, fournisseur | Compteurs Vercel lus ; Turso et Upstash non accessibles |
| 7 Polling | Corrigé et testé | Adaptation, visibilité, retour réseau, non-chevauchement, jitter, combat |
| 8 WebSocket | Corrigé et testé | Auth, recul, secours, nettoyage, présence cachée ; monde totalement déconnecté non garanti |
| 9 Turso | Audité, mesures distantes ouvertes | Transactions/fences et changements ciblés testés ; compteurs, slow queries et export manquants |
| 10 Redis | Corrigé et testé en CI | Deux instances, reprise propriétaire/checkpoint et fence ; nouvelles pannes de libération simulées |
| 11 Moteur | Profilé et testé | Douze chemins identifiés ; IA et tactique ; chemins identiques conservés |
| 12 Refactoring | Audité, extraction ciblée | Limiteur indépendant ; refonte globale différée avec justification |
| 13 Qualité | Audité et renforcé | Ruff, syntaxe, inventaire AST, erreurs et concurrence ; typage global incomplet |
| 14 Auth et sessions | Testé | Propriété, révocation, expiration, changement de mot de passe, admin, limite scrypt |
| 15 Commandes | Testé | Répétition, contenu conflictuel, concurrence, état périmé, règles serveur conservées |
| 16 Sécurité web | Audité et testé | JSON, origines, SQL, XSS, admin, headers et dépendances ; pas de pentest exhaustif |
| 17 Tests | Validés | CI trois Python/Redis/Windows/UI et contrôles locaux ; exclusions explicites |
| 18 Couverture | Mesurée | Lignes 77,76 %, branches 70,95 % ; artefact CI également produit |
| 19 Charge | Mesurée localement | 1 à 100 essais courts historiques, nouveau 40/180 s ; services distants et soak 24 h ouverts |
| 20 Interface | Testée | DOM/focus/PV, cartes, compétences, forge et erreurs ; heap long non mesuré |
| 21 Accessibilité | Automatisée, réserve manuelle | Chromium trois tailles, axe sans violation ; deux contrôles incomplets et appareils réels ouverts |
| 22 Branches | Écart documenté | Health corrigé des deux côtés ; PR #34 seulement master, publication différée |
| 23 Actions | Renforcées | Épinglage, couverture, lint, concurrence et moins de doublons ; protection reportée |
| 24 Déploiement | Existant validé, nouveau reporté | Version 82a746 publiée et vérifiée ; nouvelles corrections non déployées |
| 25 Livrables | Fournis dans la PR | Rapport, code, JSON, liens, reproduction et maintenance |
| 26 Barème | Calculé | 85/100 argumenté ci-dessous, pas de note artificiellement portée à 90 |
| 27 Priorités | Clôturées sur le périmètre accessible | P0 données/tests ; P1 ressources ; P2 pannes ; P3 CI ; P4 UI ; P5 rapport ; réserves nommées |
| 28 Validation | Partielle explicite | Intégration autorisée si verte ; publication/protection et preuves fournisseurs encore ouvertes |
| 29 Indicateurs | Mesurés ou marqués inconnus | Gains historiques, couverture et charge ; pas de faux coûts/distants avant-après |

## Score argumenté

| Catégorie | Note | Preuve et défaut restant | Confiance |
|---|---:|---|---|
| Architecture | 12/15 | Modules et frontières identifiés ; propriétaire actif et grandes fonctions encore présents | Moyenne |
| Qualité | 8/10 | Ruff, syntaxe, erreurs et concurrence renforcés ; typage/style globaux incomplets | Moyenne |
| Sécurité | 13/15 | Contrôles testés, limite scrypt corrigée, dépendances et headers vérifiés ; pas de pentest complet | Moyenne |
| Tests et fiabilité | 14/15 | 1 586 tests CI, Redis réel et cinq nouveaux tests ; pannes cloud combinées non vérifiées | Élevée sur les tests, moyenne au-delà |
| Performance | 8/10 | Polling, présence, chemins et charge mesurés ; coût global et durée longue ouverts | Moyenne |
| Multijoueur et données | 8/10 | Fence, reprise et restauration isolée ; export et rétention cloud non confirmés | Moyenne |
| Gameplay | 9/10 | Règles préservées et corpus moteur/UI ; recette complète du contenu non certifiée | Moyenne |
| Interface et accessibilité | 4/5 | Chromium trois tailles, stabilité/focus, axe ; lecteur d’écran et contrôles incomplets ouverts | Moyenne |
| CI/CD et production | 4/5 | Publication exacte validée et actions épinglées ; prod non protégée, nouvelle publication différée | Moyenne |
| Documentation | 5/5 | Statuts, causes, preuves, mesures, reproduction, réserve et maintenance disponibles | Élevée |
| **Total** | **85/100** | **Évaluation technique indicative ; 90 non atteint** | **Moyenne** |

Cette note applique le barème demandé ; elle n’est pas une mesure scientifique. Pour la réévaluer, il faut notamment certifier la restauration d’un export réel, observer les compteurs fournisseurs, exercer une panne/reprise dans un environnement autorisé, terminer la recette accessible et sécuriser la publication.

## Reproduction et maintenance

Installer les dépendances dans un environnement isolé avec `python -m pip install -c constraints.txt '.[test]' pytest-cov==7.1.0 ruff==0.16.10`. Exécuter `python -m pytest -q -rs --cov=jeuxRPG --cov-branch`, puis Ruff. Pour les scripts lancés directement depuis `scripts/`, s’assurer que les imports désignent le dépôt courant ou une wheel construite depuis son SHA ; une ancienne copie installée ne doit pas masquer les sources.

Installer l’outillage UI fixé dans la CI, puis exécuter les vérificateurs transport, polling, retry, Mira, tactile, navigation carte et administration. `python scripts/verify_http_ui.py` utilise une base temporaire. Pour Chromium/axe, installer Playwright Chromium et définir `RPG_VERIFY_HUD_LAYOUT=1`. Les captures de la CI sont dans l’artefact `hud-captures`.

Pour reproduire la charge : `python scripts/verify_load.py --seconds 180 --users 40 --combat-users 20 --poll-interval 1 --fixed-zones --max-p95 500 --output load.json`. Pour le profil : reprendre la commande stockée dans `engine-profile.json`. Les micro-bancs historiques sont reproduits avec `measure_resource_changes.py --baseline f27dabee1b4b886ea117debf18d9cb6322c03356` et les vérificateurs de polling.

À chaque PR : contrôler toutes les matrices, UI, lint, installation et performance sur le SHA exact. Chaque semaine : relire les métriques CPU/mémoire/erreurs et les dépendances ; surveiller les changements d’advisories. Sur une journée représentative : relever les compteurs Vercel, Turso et Redis en début/fin, avec nombre de joueurs et durée active. Préparer des alertes de consommation après choix des seuils ; aucune alerte ou automatisation externe n’est créée par ce rapport.

À chaque publication future : obtenir un export/sauvegarde conservé, tester sa copie isolée, protéger `prod` ou exiger un reviewer de l’environnement, puis PR `master` → `prod` avec tests verts. Utiliser le workflow qui crée un déploiement sans domaine, vérifie le SHA et les parcours, puis promeut seulement si ces contrôles passent. Ne pas contourner Vercel Authentication et ne pas réinitialiser les données pour faire passer un test.

En cas de régression après une future publication : conserver la preuve du SHA et des logs, remettre le précédent déploiement vérifié via Vercel, sans rollback destructif de la base. Cette clôture n’introduit aucune migration inverse nécessaire. Ne pas promouvoir automatiquement une version dont l’intégrité ou la restauration n’est pas confirmée.

## Réserves nécessitant une action ultérieure

1. **Protection de prod et publication des corrections : reportées par le propriétaire.** La tentative d’enregistrement de protection a demandé une vérification GitHub supplémentaire ; aucune règle nouvelle n’a été enregistrée.
2. **Comptes Turso et Upstash :** compteurs, plan réel, commandes et latences, politique de sauvegarde et export/restauration réelle. Ne jamais transmettre leurs secrets dans le chat ; utiliser leurs comptes ou les secrets GitHub prévus.
3. **Recette humaine :** deux contrôles axe incomplets, lecteur d’écran, appareils tactiles réels, connexion lente et mémoire navigateur sur longue durée.
4. **Endurance et pannes distantes :** une charge prolongée locale de trois minutes ne remplace pas 24 heures, un basculement Vercel réel ou une panne combinée Redis/Turso. Aucun essai de saturation fournisseur n’est autorisé implicitement.

Le travail accessible est livré et les réserves sont traçables. Il serait incorrect de déclarer toutes les conditions de validation satisfaites tant que ces preuves manquent.
