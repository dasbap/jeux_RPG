# Exécution de l’audit complémentaire — 11 octobre 2026

Ce rapport répond au fichier fourni `audit_jeux_RPG(2).md`. Il remplace les états opérationnels anciens, sans effacer leurs preuves. Référence de départ : `0e4f42e57e80b4097da631d66f9c30756e28212f` sur master ; production observée : `82a7461613ec748014d3cf5a97bdade88f1d1ee3`. Aucun ajout de contenu ou de règle de jeu dans ce correctif. La migration de guildes déjà fusionnée par le propriétaire est additive : tables/index nouveaux, aucune suppression.

## État des demandes

| Demande | Résultat et preuve | Limite restante |
|---|---|---|
| Protéger master/prod, checks obligatoires | Ruleset GitHub `protected` actif, sans bypass, PR et huit checks Actions requis, branche à jour, suppression/force-push bloqués ; prod ciblée exactement | Paramétrage distant, distinct du code ; zéro approbation humaine exigée dans le ruleset du propriétaire |
| Protéger le workflow à secrets | Environnement `production`, autorisation de branche prod uniquement, bypass administrateur désactivé | Secrets conservés dans GitHub ; aucune valeur extraite ; administration Turso du workflow limitée aux lectures, migration réservée à la publication sauvegardée ; ancien workflow de stockage limité à prod/production, provisionnement automatique retiré et token seulement via environnement |
| Réconcilier branches/migrations | Référence master actualisée, migration 0003 revue, version 3 et compatibility testées ; publication via PR | La production publique reste sur l’ancien SHA tant que le garde-fou de sauvegarde n’est pas levé |
| SHA exact, staging puis promotion | Workflow teste son SHA, récupère la configuration du projet exact, construit en CI puis publie `--prebuilt --prod --skip-domain`, health exige ce SHA, parcours admin/runtime puis promotion de la même URL | Nouvelle publication non certifiée avant exécution réussie du workflow |
| Correctifs Redis, fermeture/concurrence | Correctifs antérieurs conservés ; nouveaux tests de checkpoint refusé, Redis puis Turso indisponibles, mutation pendant persist et perte de propriété ; double perte de propriété simultanée reproduite (AttributeError), puis corrigée par revérification du store sous verrou | Les tests injectés ne certifient pas la disponibilité des fournisseurs réels |
| Pertes silencieuses / compteurs | Refus de checkpoint journalisé, batch non acquitté ; compteurs erreurs, refus, reprises et mutations locales abandonnées lors de perte de propriété | Compteurs par processus, remis à zéro au redémarrage ; premier chargement compte aussi comme reprise |
| Export Turso et restauration isolée | Nouveau export transactionnel en lecture, fichier privé 0600, rollback source, integrity/FK, comparaison des tables et ouverture du moteur sur copie ; séquences AUTOINCREMENT préservées, y compris après suppression du plus grand ID | Testé avec le protocole Turso simulé, y compris échec d’export et préservation des séquences ; export réel et rétention restent conditionnés à une clé publique du propriétaire |
| Conserver hors production | Workflow chiffre avec age, publie uniquement `.age`, checksum et rapport sans données, rétention GitHub 30 jours, avant toute migration | Variable publique `RPG_BACKUP_RECIPIENT` absente au contrôle ; aucune archive de comptes en clair publiée |
| Fenêtre de perte | Décrite ci-dessous, sans garantie arbitraire de cinq secondes | Une interruption avant checkpoint accepté/persisté peut perdre des mutations |
| Complexité/duplication mesurées | Ruff C901 sur référence avant et code après ; AST exact indépendant du formatage : 43 groupes, 48 occurrences supplémentaires, inchangés | Ce détecteur mesure des fenêtres exactes, pas toute similarité sémantique ; fenêtres parfois chevauchantes |
| Refactoriser create_app/_dispatch/advance | Enregistrement WebSocket, dispatch GET et avancée d’un mob extraits, interfaces publiques préservées | Helpers encore complexes ; poursuite progressive plutôt que réécriture globale |
| Ruff/formatage progressifs | E4/E7/E9/F/B/UP/SIM/C4 activés ; quatre fichiers critiques + types formatés ; 466 → 458 alertes sur scan intégral | Exceptions historiques explicites par fichier/code, plafonnées en CI ; huit alertes supprimées, pas 466 |
| Types aux interfaces critiques | TypedDict requête/réponse et batch, annotations transport/sauvegarde | Corps JSON encore Any ; ce n’est pas un typage complet ni une preuve de mypy strict |
| Noms/exceptions | Helpers nommés par responsabilité ; erreurs checkpoint et perte de propriété explicites et comptées | Les exceptions larges aux frontières de transport restent nécessaires ; pas de reformatage massif hors périmètre |
| Reconstruction/sérialisation d’état | Cache existant par personnage/révision avec ancienneté 200 ms conservé ; signatures de sessions inchangées : zéro requête SQL au micro-banc ; confirmations compactes et bundles existants conservés | Profil actuel garde les vues et snapshots comme coûts importants ; aucune élimination de toutes les conversions JSON revendiquée |
| Chemins/static/IA | Dijkstra reconstruit via prédécesseurs au lieu de recopier la route dans chaque entrée ; LRU et conditions d’invalidation inchangés ; 298 routes strictement identiques | CPU à froid −6,04 % sur ce banc ; second échantillon 45 routes légèrement plus lent ; aucun gain global garanti |
| Profiler avant/après | Micro-banc différentiel chemins et ressources ; profil cProfile actuel sur 234 tests conservé | Temps cProfile se recouvrent et sont instrumentés ; les profils historiques n’ont pas un périmètre identique |
| Écritures état inchangé | Capture/pending batch et signatures existants conservés, tests de sauvegarde et mutation concurrente passent | Pas de faux compteur de commandes fournisseur déduit des appels Python |
| Mesurer Turso/Redis réels | Vérificateur de publication exige runtime mémoire et `trips=0` sur les états, sauvegarde pending à zéro ; consommation Vercel réellement relue | Tableau Vercel Upstash « No data available yet » ; compteurs et latences par opération Turso/Redis distants non certifiés |
| Frontend hash/cache | URL statiques versionnées, caches conditionnels existants conservés et couverts par tests | Revalidation du nouveau déploiement public attend sa publication |
| Panneaux/DOM/listeners | Signatures de panneaux conservées ; parcours HUD démontre nœuds et focus stables sur 40 actualisations ; 500 reconnexions avec 1 listener document, 0 timer après fermeture | Socks/horloge simulés ; contrôle Chromium vert sur 100 rendus de chauffe + 500 mises à jour, DOM/listeners/heap après GC ; aucun remaniement DOM sans preuve de gain |
| Couverture progressive | 1 606 tests locaux réussis, 8 ignorés ; 78,22 % lignes / 71,22 % branches ; planchers CI 77/70, sans exclusion ajoutée | Objectifs 85/80 pas atteints ; modules transport et autorisations branches prioritaires |
| Scénarios sauvegarde/permissions | Tests antérieurs conservés plus nouveaux tests panne, sauvegarde, export et concurrence ; préparations de login revalidées après rotation/suspension et invitations non transférables à un tiers ; CI Redis réel sur trois versions Python | Les scénarios de panne injectés ne sont pas un chaos test de services de production |
| Tests ignorés | Inventaire explicite ci-dessous ; Redis réel activé dans Actions et éditeur Tk testé sur Windows | Deux modules de carte mis en pause et bot externe toujours indisponibles dans ce dépôt |
| Dépendances et actions | Actions épinglées à SHA conservées ; versions Ruff/age de distribution officielle ; contraintes existantes conservées ; nouveaux scans Python et npm : zéro vulnérabilité connue, relancés par la CI à chaque PR/push protégé | Scan de dépendances ≠ pentest ; aucune certification de sécurité totale |
| INP/LCP/mémoire téléphone | Parcours automatisés maintenus, aucun chiffre physique inventé | Téléphones réels et lecteur d’écran humain indisponibles ici ; recette manuelle nécessaire |
| Endurance non productive | 40 combats, 300 s : 12 000 états, 3 000 déplacements, zéro erreur, p95 100,48 ms, RSS max 57,86 Mio | Endurance 30 min validée : 72 000 états, 18 000 déplacements, 40 combats encore actifs, zéro erreur, p95 61,82 ms, RSS max 58,73 Mio ; aucune validation 24 h |
| Documentation | README pointe ce rapport ; anciens rapports marqués historiques, preuves retenues | Historique volontairement conservé, pas de suppression de rapports |
| CI redondante/budgets | Concurrence CI existante conservée ; lint, matrice Python, builder Windows, wheel installé et navigateur ont des objets distincts ; budgets complexité, duplication exacte, dette lint, couverture, chemins et p95 ajoutés ; trois builds de wheel redondants retirés, wheel/sdist/install conservés dans package | Tests de publication conservés pour vérifier le SHA exact ; ils ne sont pas supprimés comme simple doublon |

## Preuves quantitatives

La complexité cyclomatique réelle passe de 53 à 24 pour `create_app`, de 53 à 43 pour `_dispatch`, et de 48 à 19 pour `advance`. Les helpers extraits ont respectivement des responsabilités transport/GET/mob ; `_register_socket` reste à 30 et `_advance_mob` à 30. Ces plafonds sont contrôlés par `scripts/quality_budget.py`.

Les fichiers JSON voisins contiennent couverture, complexité, duplication, inventaire Ruff, profil, comparaison de chemins, ressources et endurance. `resource-comparison.json` mesure SQLite et une présence instrumentée locale, pas des services distants : 100 admissions font 100 lectures du registre et un renouvellement ; les signatures sans session dirty ne font aucune requête SQL avant comme après. Sur 45 routes, les résultats sont identiques et le CPU médian passe de 0,18534 à 0,19112 s ; la variance et le choix des cas interdisent de généraliser le −6,04 % du banc de 298 cas.

Le profil actuel place `tutorial.view`, `service._snapshot`, `service.state` et `world.view` parmi les plus grands temps cumulés. Ne pas additionner ces temps imbriqués. Le second banc différentiel sur 298 cas mesure 0,78849 → 0,71982 s CPU (−8,71 %), mais le pic tracemalloc passe de 377 936 à 422 840 octets (+11,9 %, allocations Python, pas RSS). Le compromis améliore le CPU de ce banc au prix d’une petite allocation transitoire supplémentaire ; budget CI CPU relatif +25 % et pic tracé 1 Mio.

Les règles tactiques continuent d’être recalculées lorsqu’une décision dépend d’un état mutable ; aucun cache d’IA sans clé d’invalidation démontrée n’est introduit.

## Persistance et reprise

La capture planifie normalement une sauvegarde à environ cinq secondes, avec de nouvelles tentatives en cas d’erreur. Ce délai est un échéancier nominal : il n’est **pas un RPO garanti**. Une sauvegarde peut être retardée par le réseau, la charge, des refus de fence ou les deux fournisseurs indisponibles. Le processus garde son batch en mémoire tant qu’il reste propriétaire ; un checkpoint Redis accepté peut permettre la reprise même si Turso a échoué. Si le processus meurt avant un checkpoint accepté et durablement conservé, ou si les fournisseurs perdent leurs dernières données, les changements depuis le dernier point récupérable peuvent disparaître. En cas de panne prolongée, la fenêtre n’a pas de borne de cinq secondes.

Un ancien propriétaire ne doit jamais contourner le fencing pour écrire un état possiblement obsolète. Lorsqu’il perd sa lease avec des mutations encore locales, la fermeture les signale par un log d’erreur et un compteur ; leur récupération dépend du dernier checkpoint accepté. Les nouveaux compteurs `X-RPG-Save-Failures`, `X-RPG-Checkpoint-Rejections`, `X-RPG-Owner-Recoveries` et `X-RPG-Owner-Pending-Drops` complètent `X-RPG-Save-Pending`. Ils ne sont pas une métrique globale persistante.

## Sauvegarde : dernière configuration indispensable

Installer age depuis une source officielle puis générer une identité localement :

```sh
age-keygen -o rpg-backup.key
age-keygen -y rpg-backup.key
```

Conserver `rpg-backup.key` privé, avec une copie sûre hors de GitHub. Configurer seulement la sortie **publique** `age1…` dans la variable GitHub Actions `RPG_BACKUP_RECIPIENT` (environnement production ou dépôt). Ne pas mettre la clé privée dans les secrets GitHub et ne pas l’envoyer en conversation. Documentation de référence : [age](https://github.com/FiloSottile/age).

Le workflow vérifie la présence de cette variable avant toute écriture de production. Après configuration, lancer `Publication Vercel jeux-rpg` sur prod : tests exacts → export Turso en lecture → restauration isolée → chiffrement → upload réussi → migration additive → build CI du projet exact → staging préconstruit → health/parcours → promotion. Toute étape échouée empêche la promotion. Une variable non vide mais mal formée échoue au chiffrement avant migration. La sauvegarde ne modifie pas la source ; la copie est supprimée du runner, l’archive chiffrée reste 30 jours dans Actions. La rétention n’est pas un archivage éternel : télécharger les archives nécessaires avant expiration.

Pour vérifier une archive téléchargée :

```sh
sha256sum -c backup-checksum.txt
age -d -i rpg-backup.key -o restored.sqlite3 production-before.sqlite3.age
python scripts/verify_backup.py restored.sqlite3
```

Les comptes et tokens de production ne sont jamais utilisés dans les fixtures d’endurance.

Les fixtures CI testent la chaîne de chiffrement/déchiffrement ; elles n’ont pas accès à la clé privée du propriétaire. Le déchiffrement d’une archive réelle par cette identité doit donc être confirmé par le propriétaire. Ne pas remplacer la base de production pour faire ce contrôle.

## Tests ignorés et recette physique

- `test_realtime.py:318` : Redis réel absent en local ; service Redis et `RPG_TEST_REDIS_URL` fournis dans les workflows CI/publication.
- `test_map_layout_editor.py:52` : bibliothèque Tk `libtcl9tk9.0.so` absente localement ; job builder Windows dédié.
- `test_storage_level_exp.py` : quatre tests dépendent du bot externe `bot.game.storage`, absent ; pas de faux package ajouté pour les faire passer.
- `test_town_pois.py` et `test_world_map_town_seed.py` : modules historiques mis en pause par leurs auteurs. Les réactiver demanderait de reprendre un périmètre fonctionnel suspendu.

Recette physique restante : Chrome Android et Safari iPhone, exploration puis combat prolongé, appui long, onglet caché, perte réseau/reconnexion, vérification du focus clavier et lecteur d’écran. Mesurer INP/LCP et heap sur l’appareil, avec modèle/OS/navigateur/date/scénario ; les chiffres d’émulation ne remplacent pas ces preuves.

## Production observée

Tableau Vercel relu le 11 octobre, période affichée 11 septembre 07:00 → 11 octobre 07:00, données retardées jusqu’à une heure : CPU actif 2 h 14 / 4 h (environ 56 %), mémoire provisionnée 39,3 / 360 GB-h, invocations 2 106 / 1 000 000, transfert rapide 93,84 MB / 100 GB. L’aperçu des six dernières heures indiquait 48 invocations et 0 % d’erreurs ; cela ne certifie pas l’absence d’incidents historiques. Upstash n’affiche pas de données d’usage exploitables dans cette vue. Le connecteur API Vercel retourne 404 pour le projet malgré son existence confirmée dans le dashboard connecté : aucun nouveau token demandé pour contourner cette limite.

Le score 76/100 fourni et l’objectif 85–90 restent des appréciations du document d’entrée. Ce travail n’attribue pas un nouveau score certifié tant que publication, sauvegarde réelle et recette physique n’ont pas leurs preuves.

## Validation GitHub intermédiaire

PR #39, tête `f4180702740e303e06c07f159ae6f89e9840ac32` : huit checks verts, runs 38144492651 (lint), 38144492619 (package), 38144492625 (performance), 38144492620 (matrice Python, Windows, UI). La fixture age chiffre/déchiffre avec succès ; couverture CI 3.12 : 78,33 % lignes / 71,48 % branches. Ces résultats ne remplacent pas les checks de la tête finale.

## Deuxième validation GitHub

Tête `426019f1f23d4b27e689d5b852df4147b8d7f097` : huit checks verts (runs 38145285922, 38145285920, 38145285903, 38145286094). Python 3.12 : 1 606 réussis, 7 ignorés, couverture 78,36 % lignes / 71,55 % branches. Redis réel couvre le scénario localement ignoré. Les trois viewports Chromium passent les budgets mémoire : listeners inchangés, 18 nœuds de moins après GC, heap retenu +2,44 à +2,64 %. Il ne s’agit pas d’INP sur un téléphone physique.

L’endurance de 30 minutes est isolée sur SQLite/HTTP local, à 40 lectures par seconde au total et déplacements toutes les quatre secondes. Les 30 échantillons confirment 40 combats actifs et serveur/ticker vivants. Le RSS maximal croît de 54,61 à 58,73 Mio ; cette croissance observée ne démontre pas l’absence de fuite sur 24 heures. Aucun trafic de charge n’a été envoyé à la production.
