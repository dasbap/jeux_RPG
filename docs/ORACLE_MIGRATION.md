# Migration Oracle : moteur et recette D1

Branche de travail : `migration/oracle-single-d1`. La production reste sur
Vercel/Redis/D1. Le mode persistant et sa première recette D1 distante sont
réalisés. Le Worker de test utilise une ancienne base fictive, séparée de la
production et de la copie importée. Aucune VM Oracle n'est encore créée.

Le [rapport du 13 novembre](oracle-test-20261113/REPORT.md) contient les mesures
de 40 WebSockets, les vérifications de reprise et le parcours Chromium.
Le [kit d'exploitation Oracle](ORACLE_OPERATIONS.md) prépare maintenant cloud-init,
systemd, Caddy, DuckDNS et les workflows de déploiement/sauvegarde. Il n'est pas
encore exécuté sur une VM ; aucun compte Oracle n'est disponible.

## Mode mono-instance disponible

`RPG_RUNTIME_MODE=single` sélectionne un moteur ASGI persistant avec D1.
Le défaut reste `distributed` pour préserver le déploiement existant. Le mode
`single` refuse Vercel et tout backend autre que D1. Les URL Redis, même
héritées d'une ancienne configuration, sont ignorées. Les limites de requêtes
et la présence restent locales. Le paquet Python Redis reste installé pour
la compatibilité du mode distribué.

Au démarrage ASGI, le moteur vérifie le schéma, demande au Worker l'opération
authentifiée `claim_snapshot`, puis restaure le snapshot complet. D1 incrémente
`runtime_fence` et lit les tables dans le même lot atomique sur le primaire.
L'attribution ne dépend pas de l'horloge de la VM. Aucun nouveau schéma n'est
nécessaire : les deux triggers de génération existants restent obligatoires.

Les sauvegardes utilisent toujours les lots D1 existants. Une confirmation
toutes les cinq secondes, même sans changement, permet de détecter un moteur
remplacé. D1 rejette immédiatement ses anciennes écritures ; à réception du
rejet, le moteur suspend commandes et simulation et `/ready` renvoie 503.
Deux processus peuvent donc encore servir de la RAM pendant la fenêtre de
détection : lancer **un seul worker**, sans rechargement automatique, et ne pas
utiliser ce mécanisme comme un système d'élection ou de haute disponibilité.

L'authentification par compte reste obligatoire hors Vercel, y compris pour
la première trame WebSocket. L'inscription historique locale est désactivée.
Le transport HTTPS/WSS conserve les contrôles d'origine et d'hôte. Derrière un
proxy, transmettre le schéma HTTPS et ne faire confiance aux en-têtes transférés
que depuis ce proxy.
La page servie en mode `single` configure `/api/ws` comme transport temps réel,
y compris lorsque son domaine n'est pas un domaine Vercel.

`/health` reste un contrôle de processus. `/ready` vérifie qu'un moteur est
chargé et que sa dernière sauvegarde n'a pas échoué ; il ne fait pas une requête
D1 à chaque appel. Une panne distante peut donc apparaître avec un retard.

La fermeture du coordinateur capture les changements et exige une réponse D1
positive, même sans lot en attente. En cas d'échec, elle lève une erreur et
conserve le moteur et ses tâches pour réessayer. Cela ne peut pas empêcher
Uvicorn, systemd, le système ou un administrateur de terminer le processus :
le service VM `jeuxRPG.multiplayer.host` ajoute désormais un drainage qui
confirme D1 avant de laisser Uvicorn quitter sur signal. Le futur contrôleur
d'inactivité devra gérer aussi les activations concurrentes. Aucun arrêt pour
inactivité n'est activé par cette étape.

## Préproduction isolée

Les tests Python utilisent un substitut D1 en mémoire, sans secrets ni réseau.
`scripts/verify_d1_worker.mjs` exécute le véritable Worker sur SQLite local,
avec lots atomiques, restauration, générations successives et rejet des anciens
moteurs. Ces seuls tests ne valident pas Oracle ni Cloudflare D1 réel.

La recette distante utilise `cloudflare/wrangler.oracle-test.json` : Worker
`jeux-rpg-oracle-test`, base fictive `jeux-rpg-preview`. Ne pas utiliser
`wrangler.preview.json` : sa cible contient une copie importée de comptes
réels, comme l'explique [D1_PREPRODUCTION.md](D1_PREPRODUCTION.md). Publier le
Worker modifié **sur la cible oracle-test seulement** avant de lancer le moteur.
Un ancien Worker refusera `claim_snapshot` : le démarrage échouera sans repli.
Ne pas réutiliser un environnement contenant des données de joueurs réels.

Avec une connexion Wrangler existante, le script ci-dessous contrôle le nom et
l'identifiant de la base ainsi que la vacuité des tables, puis configure le
secret et déploie le Worker de test. Il ne crée aucune base et ne change aucun
binding de production. Le fichier de secrets est
`.data/oracle-test/runtime.env`, hors Git.
Installer aussi les dépendances de test (`python -m pip install -e ".[test]"`)
pour disposer du client HTTP utilisé par la recette.

```sh
python -m scripts.deploy_oracle_test --wrangler-js CHEMIN_VERS_WRANGLER_JS
python -m scripts.verify_single_preview --users 40 --combat-users 20 --seconds 60
```

La recette crée ses comptes fictifs hors de la période mesurée, ouvre de vrais
WebSockets vers un moteur ASGI sur le poste, contrôle D1 et la reprise, puis
supprime les lignes fictives. La préparation refuse une base non vide ; le
nettoyage refuse des comptes inattendus. Ne pas lancer deux recettes en
parallèle. Le rapport est dans `.data/oracle-test/report.json` et ne contient
aucun jeton ni mot de passe. La panne D1 est une injection locale dans le
transport du moteur de test.

Pour le parcours navigateur, Playwright et Chromium doivent être installés
séparément. Sur ce poste, ils sont disponibles sous `.data/browser-tools` et
`.data/browser-binaries` :

```sh
python -m scripts.verify_single_browser --playwright-module .data/browser-tools/node_modules/playwright
```

Le navigateur vérifie la connexion, le choix du personnage, l'affichage et le
WebSocket avant et après redémarrage. Ses captures et son rapport restent dans
`.data/oracle-test/`. Les identifiants fictifs passent par l'entrée standard du
sous-processus et ne sont pas inscrits dans les rapports.

Copier [l'exemple de configuration](../deploy/oracle/.env.example) dans un
fichier hors Git, par exemple `.data/oracle-preview.env`, puis remplacer chaque
valeur avec les paramètres de préproduction. Aucun secret ne doit être envoyé
au navigateur. Avec les dépendances du projet installées :

```sh
python -m uvicorn app:app --host 127.0.0.1 --port 8080 --workers 1 --env-file .data/oracle-preview.env
```

Le fichier `.env` racine historique n'est pas chargé par cette commande.
Vérifier aussi les variables déjà exportées dans le shell : Uvicorn ne les
écrase pas avec le fichier. En particulier, retirer `VERCEL` et confirmer la
cible D1 avant de lancer le processus. `RPG_PUBLIC_ORIGIN` désigne pour cette
recette l'origine HTTPS du moteur et de son interface servie au même endroit.
La séparation de l'interface Vercel sera traitée avec le routage et le réveil.

Vérifications locales reproductibles :

```sh
python -m pytest test/test_single_runtime.py test/test_d1_client.py test/test_d1_configuration.py test/test_redis_configuration.py test/test_realtime_failures.py test/test_realtime.py test/test_realtime_health.py test/test_account_security.py test/test_accounts_social.py -q
node scripts/verify_d1_worker.mjs
```

## Suite de la migration

1. Première recette D1 isolée réalisée : comptes, personnages, progression,
   sauvegarde/reprise, panne de transport injectée, générations concurrentes,
   charge de 40 WebSockets et Chromium. Refaire ces essais sur la VM Oracle.
2. Kit Oracle ARM64 préparé : cloud-init, secrets hors dépôt, systemd, Caddy,
   DuckDNS, supervision et sauvegardes indépendantes. Créer les comptes et la
   VM, puis vérifier l'installation réelle. Aucune ressource payante automatique.
3. Ajouter le contrôleur externe authentifié et son verrouillage : réveil,
   reconstruction depuis boot volume ou GitHub, tentatives bornées si la
   capacité gratuite est indisponible.
4. Ajouter l'inactivité : zéro joueur pendant une heure, sauvegarde confirmée
   puis arrêt moteur ; cinq heures supplémentaires sans activation, arrêt VM.
   Toute demande de joueur annule ou réinitialise les compteurs.
5. Intégrer l'écran de réveil Vercel, le routage HTTP/WS et la reconnexion,
   en gardant le solo hors ligne accessible.
6. Persister les événements du monde vivant, leur reprise déterministe et
   leur exécution unique ; tester les pannes et les restaurations.
7. Bascule contrôlée : sauvegarde indépendante vérifiée, arrêt des écrivains
   Vercel, confirmation D1, démarrage du seul moteur Oracle, recette, routage,
   puis retrait de Redis. Un retour arrière doit reprendre les écritures D1
   récentes et ne doit jamais relancer deux architectures en concurrence.

La capacité à 40 joueurs en production, la disponibilité Always Free et le réveil
ne sont pas validés par cette recette locale avec D1 distant. Les données présentes seulement en RAM
restent exposées à une panne brutale.
# Archive : Oracle abandonné le 14 novembre 2026

Le moteur mono-instance D1 reste réutilisé. Les instructions Oracle ci-dessous sont
historiques ; voir [la recette Render Free](RENDER.md) pour la cible active.

