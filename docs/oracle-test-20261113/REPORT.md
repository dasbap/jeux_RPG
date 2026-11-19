# Recette mono-instance D1 — 13 novembre 2026

## Parcours vérifié

Le joueur se connecte par compte, sélectionne son personnage et joue via
HTTP/WebSocket. Le moteur Python reste en RAM et sauvegarde dans D1. Après
redémarrage, le compte, la session et la progression sont restaurés.

La recette utilise un moteur ASGI sur le poste Windows, le Worker dédié
`jeux-rpg-oracle-test` et la base fictive existante `jeux-rpg-preview`
(`bf29ab72-c4a8-440b-a106-da6badde250c`). Les tables durables du jeu étaient
vides avant la préparation. Aucun accès en écriture n'a visé la production
ou la copie importée `jeux-rpg-import-preview`. Aucune VM ni base nouvelle
n'a été créée. Le Worker de test reste déployé ; aucun moteur local de recette
ne reste lancé après les vérifications.

## Charge réelle

[Résultats JSON](load40.json) : 40 sockets TCP WebSocket authentifiées et
ouvertes simultanément, pendant une charge configurée de 60 secondes ;
20 sessions de combat indépendantes et 20 sessions en ville.

| Mesure | Résultat |
| --- | ---: |
| Lectures d'état réussies | 2 375 |
| États poussés reçus | 2 015 |
| Déplacements de combat réussis | 300 |
| Conflits d'action | 0 |
| Erreurs de transport ou réponse | 0 |
| Latence d'état p50 / p95 / p99 | 270 / 439 / 517 ms |
| Latence de déplacement p50 / p95 / p99 | 357 / 513 / 547 ms |
| Checkpoints confirmés à la fin de la charge | 11 |
| Échecs de sauvegarde pendant la charge | 0 |
| Volume applicatif reçu par les clients de test | 252 372 749 octets |

Les clients demandent un état complet environ chaque seconde et reçoivent
aussi les diffusions du moteur. Les combats utilisent des personnages avec
des PV augmentés pour prolonger l'essai. Le volume ci-dessus n'est pas une
estimation du trafic de production : ce scénario cumule lectures complètes
et états poussés, et ne mesure pas les octets facturés sur le réseau.

## Sauvegarde et incidents

- Après la charge, le dernier lot est confirmé et aucun changement ne reste
  en attente.
- Une panne de transport D1 est injectée dans le moteur de test : la progression
  modifiée reste en RAM, `/ready` passe à 503 et la fermeture du coordinateur
  est refusée. Après rétablissement, la sauvegarde est confirmée et `/ready`
  repasse à 200. Cela ne simule pas une panne réelle du service Cloudflare.
- Un nouveau cycle de démarrage recharge les 40 comptes, personnages et
  sessions ; la connexion par mot de passe et la progression modifiée sont
  contrôlées. Les 40 sockets se reconnectent, sans erreur.
- Un moteur concurrent obtient une nouvelle génération D1. L'ancien moteur
  détecte le rejet au prochain checkpoint, devient indisponible et refuse
  les commandes. La détection reste périodique, pas instantanée.
- Les lignes fictives ont été retirées après la recette. Seules les métadonnées
  restent dans la base d'essai.

## Navigateur

[Résultats Chromium](browser.json) : connexion par mot de passe, sélection
du personnage, affichage du jeu et WebSocket connecté, avant puis après un
redémarrage du moteur. Aucune erreur JavaScript de page ni réponse API 5xx
n'a été observée dans ces deux parcours.

Le contrôle a révélé que le client n'activait spontanément les WebSockets que
sur un domaine Vercel. En mode `single`, le serveur injecte désormais la
métadonnée `rpg-realtime-url=/api/ws` dans sa page HTML. Le mode distribué
existant conserve son comportement.

## Portée

Ce résultat valide une première intégration du moteur mono-instance avec un
vrai D1 distant. Il ne valide **pas** 40 joueurs sur Oracle ARM64, un combat
commun à 40 joueurs, l'endurance, TLS/Caddy, la latence Internet vers les
joueurs, ni le délai action → affichage chez les autres clients. Il ne mesure
pas le coût d'exploitation et ne garantit pas la disponibilité Always Free.

La prochaine étape est la préparation de l'hôte Oracle, puis la reproduction
de la recette sur cet hôte. L'arrêt automatique, le contrôleur externe et la
bascule de production restent à développer.
