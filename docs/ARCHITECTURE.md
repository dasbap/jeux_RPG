# Architecture et état actuel

Référence d’exploitation mise à jour le 13 novembre 2026. Les rapports d’audit
datés décrivent leurs anciennes révisions ; ils ne remplacent pas ce document.

## Modes d’exécution

| Mode | Interface et moteur | Persistance |
| --- | --- | --- |
| Production multijoueur | HTML/JavaScript, FastAPI/ASGI Python sur Vercel, WebSocket `/api/ws` et HTTP | Cloudflare D1 via un Worker privé ; SQLite en RAM pendant la simulation |
| Serveur local | Même moteur Python, serveur HTTP local | Fichier SQLite local |
| Solo hors ligne | Interface embarquée, moteur Python exécuté dans le navigateur avec Pyodide | Sauvegarde locale du client, sans accès D1 ni Redis |

La production a basculé de Turso vers **Cloudflare D1 le 6 novembre 2026**.
Le 13 novembre, le [healthcheck public](https://jeux-rpg.vercel.app/health)
renvoie `status=ok` et `database_backend=d1`. La variable de l’environnement
GitHub `production` est également `RPG_DATABASE_BACKEND=d1`.
Les preuves du transfert sont dans [D1_PRODUCTION.md](D1_PRODUCTION.md).

Le contenu des cartes, PNJ, dialogues, quêtes, équipements et réglages de jeu
provient du Builder. Le projet éditable est dans `projects/authored` et son
export embarqué dans `jeuxRPG/maps`. Voir le [guide du Builder](BUILDER_GUIDE.md).

## Simulation, coordination et sauvegardes

Le propriétaire du moteur simule les parties dans SQLite en mémoire. Redis
sert à l’élection et au renouvellement du bail, au relais entre instances et
aux limites distribuées. La présence de jeu est maintenue en RAM par le moteur.
Redis n’est pas la base durable des comptes, inventaires ou quêtes.

Le moteur charge D1 à sa prise de rôle et enregistre les lots de changements
via `jeuxRPG/multiplayer/d1_client.py` et `cloudflare/d1-worker.mjs`.
Le Worker authentifie les appels serveur, applique les lots atomiques et refuse
les générations de moteur périmées. Les lectures d’état du propriétaire sont
servies en RAM ; elles n’interrogent pas D1 à chaque rafraîchissement.

La capture planifie normalement une sauvegarde après cinq secondes. Ce délai
ne garantit pas une perte maximale de cinq secondes : une panne peut retarder
la persistance, et les changements uniquement en RAM peuvent être perdus.
Voir [realtime.md](realtime.md) pour les conditions de reprise.

Turso est l’ancien backend et une source de récupération verrouillée.
Son adaptateur et ses outils d’export restent disponibles. Une panne D1 ne
déclenche aucun retour automatique vers Turso. Après des écritures sur D1,
réactiver l’ancienne base sans reprendre ces écritures perdrait la progression.
La compatibilité historique du code sélectionne encore Turso si
`RPG_DATABASE_BACKEND` est absent : la valeur `d1` doit rester explicite en
production et dans toute préproduction D1.

## Capacité et fréquence des états

Le Builder configure actuellement `rules.social.realm_capacity` à **40 joueurs
actifs par serveur logique**. Les WebSockets sont aussi plafonnés par instance
de transport avec cette valeur. Ce sont deux contrôles distincts ; le plafond
des sockets d’une instance n’est pas un compteur global de toutes les instances.
La publication utilise un serveur logique (`RPG_RUNTIME_REALMS=1`).

Le tick de simulation est programmé toutes les 200 ms. Sur le propriétaire,
la diffusion périodique des états est programmée toutes les 150 ms jusqu’à
quatre présences, 500 ms jusqu’à seize, puis une seconde. Les relais restent
à une seconde. Ces intervalles ne garantissent pas la latence sous charge.
Les commandes reçoivent leur réponse dès leur traitement ; les autres joueurs
peuvent attendre la prochaine diffusion pour voir le changement.

## Mesures disponibles et limites

Le [rapport du 11 octobre](audit-20261011/load-40-180s.json) contient un essai
local de 40 utilisateurs pendant 180,59 secondes : 20 sessions de combat
indépendantes et 20 en ville, 7 200 lectures d’état et 900 déplacements,
aucune erreur, latence au 95e percentile de 206,01 ms.

Cet essai utilise HTTP et SQLite local, à une ancienne révision. Il ne mesure
ni 40 WebSockets sur Vercel/Redis/D1, ni 40 joueurs dans un combat commun.
Les recettes D1 réelles prouvent le transfert et la reprise documentés ; elles
ne constituent pas une mesure de charge à 40 joueurs.

La capacité de production à 40 joueurs reste donc à mesurer sur la version
actuelle : délai action → affichage chez les autres clients, erreurs,
reconnexions, perte du propriétaire, temps de sauvegarde et consommation des
services Vercel, Redis, Workers et D1. Les tests locaux et les quotas théoriques
ne garantissent pas à eux seuls cette capacité.

## Branches et documentation

`master` contient les changements intégrés ; `prod` désigne la version publiée.
Une modification de `master` ne publie pas automatiquement le site. Le workflow
de publication cible `prod`. Les anciens travaux ont des tags d’archive ; les
branches de migration citées dans les rapports historiques ne sont plus actives.

- [Déploiement et variables](VERCEL.md)
- [Temps réel et sauvegardes](realtime.md)
- [Bascule D1 de production](D1_PRODUCTION.md)
- [Adaptation D1 réalisée](CLOUDFLARE_D1_MIGRATION.md)
- [Worker et outils de recette](../cloudflare/README.md)
