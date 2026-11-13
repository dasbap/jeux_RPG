# Archive : Oracle abandonné le 14 novembre 2026

Le dossier `deploy/oracle` a été supprimé. Ce document conserve le plan initial ;
ne pas exécuter ses instructions. La recette active est décrite dans [RENDER.md](RENDER.md).


# Installation et automatisation Oracle

## État au 13 novembre 2026

Le kit d'installation, les unités systemd, le drainage avant arrêt, la mise à
jour DuckDNS et les workflows sont préparés sur la branche de migration.
Les changements restent locaux. Le propriétaire s'est depuis connecté à son
compte Oracle dans Brave ; aucune VM n'est créée. Le
[contrôle du brouillon et des quotas](oracle-test-20261113/COST_CHECK.md)
confirme Paris comme région principale et 200 Go de stockage Free Tier disponibles.
Aucun workflow Oracle n'est activé ou exécuté sur GitHub.
La production Vercel/Redis/D1 conserve son fonctionnement.

| Élément | Cible retenue |
| --- | --- |
| Interface | `https://jeux-rpg.vercel.app` |
| Moteur autoritaire | Ubuntu 24.04 ARM64 sur Oracle Always Free |
| DNS du moteur | `jeux-rpg.duckdns.org`, à réserver/confirmer dans le compte DuckDNS |
| HTTPS et WebSocket | Caddy → Python sur `127.0.0.1:8080` |
| Données durables | Cloudflare D1 ; aucune migration de base |
| DNS après reconstruction | Mise à jour par le contrôleur externe avec la nouvelle IP Oracle |

Le client séparé sur Vercel, le réveil, l'arrêt après inactivité et le contrôleur
OCI complet restent à développer. Le kit actuel sert d'abord à la préproduction
avec le Worker D1 fictif `jeux-rpg-oracle-test`. Son contrôle de configuration
refuse le Worker de production et la copie importée.

## Première installation

1. Créer et vérifier le [compte Oracle](https://signup.cloud.oracle.com/).
   Vérifier l'éligibilité Always Free et les quotas dans la région principale.
   La documentation Oracle consultée indique actuellement un total A1 gratuit
   équivalent à **2 OCPU et 12 Go de RAM** pour les comptes Always Free.
   Ce n'est pas une réservation de capacité et aucun repli payant n'est prévu.
   [Référence Oracle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).
2. Dans [DuckDNS](https://www.duckdns.org/), réserver ou confirmer la propriété
   de `jeux-rpg.duckdns.org`. Conserver son jeton sur le futur contrôleur externe,
   hors dépôt. Le nom choisi n'a pas été enregistré ni modifié par ces travaux.
3. Publier les changements revus et noter leur commit complet. Le bootstrap
   télécharge **ce commit précis**, pas une branche mouvante. Il refusera un
   ancien commit ne contenant pas le service VM.
4. Générer le cloud-init, sans secret :

   ```sh
   python -m scripts.render_oracle_cloud_init --revision COMMIT_COMPLET_PUBLIE --output .data/oracle-cloud-init.json
   ```

5. Créer dans la console Oracle une VM éligible Always Free en ARM64, avec
   Ubuntu 24.04, sa clé SSH publique et ce cloud-init. Contrôler les quotas
   de calcul **et** de stockage avant validation. La création reste manuelle
   à ce stade ; aucun outil fourni ne provisionne de ressource OCI.
6. Autoriser TCP 80 et 443 dans les règles réseau OCI. SSH 22 doit être
   accessible depuis les postes ou runners de déploiement autorisés. Le kit
   ouvre 80/443 dans le pare-feu IPv4 de l'hôte en préservant les règles
   existantes ; le port 8080 reste lié à la boucle locale.
7. Le cloud-init crée l'utilisateur système `jeux-rpg`, installe Python/Caddy,
   télécharge le commit et prépare sa release. Il ne contient pas `runtime.env`
   et ne démarre pas le moteur sans ce fichier privé.

Le générateur accepte aussi `--domain` pour une autre adresse ou une chaîne
vide pour préparer l'hôte sans activer Caddy. Il ne contient aucune clé privée,
aucun jeton D1/DuckDNS et aucune commande de création d'une VM payante.

## Secrets et activation de la préproduction

Copier [l'exemple du moteur](../deploy/oracle/.env.example) en
`/etc/jeux-rpg/runtime.env`, appartenant à root, permissions `0600`. Renseigner
le jeton du **Worker fictif** et un secret administrateur indépendant. Garder
`RPG_DEPLOYMENT_STAGE=preview` et `RPG_RUNTIME_REALMS=1`.

Systemd lit ce fichier et transmet les variables au processus. Il ne faut pas
placer ces secrets dans cloud-init, dans une URL publique ou dans le frontend.
Le service ne charge pas de fichier `.env` depuis le dépôt : son répertoire
de travail est `/var/lib/jeux-rpg`.

Sur la VM, après installation du fichier privé :

```sh
sudo /usr/local/sbin/jeux-rpg-deploy COMMIT_COMPLET_PUBLIE
sudo systemctl status jeux-rpg.service
sudo journalctl -u jeux-rpg.service --no-pager -n 100
```

Le déploiement construit la nouvelle release pendant que l'ancien moteur
tourne, vérifie la configuration et le schéma D1 **sans prendre de génération**,
puis demande l'arrêt de l'ancien service. Il attend son arrêt avant de changer
le lien `current`, démarre le seul nouveau moteur et vérifie `/ready`.
Les anciennes releases sont conservées pour inspection. Il n'y a pas de
suppression ou de retour arrière forcé si le contrôle échoue. Un échec de
construction laisse une release incomplète à inspecter avant une nouvelle
tentative ; il ne remplace pas le moteur actif.

Le fichier `caddy.env` contient seulement `RPG_ENGINE_HOST=jeux-rpg.duckdns.org`.
Caddy obtient et renouvelle le certificat lorsque DNS et les ports publics
sont utilisables. Il relaie aussi les WebSockets et conserve l'hôte demandé.
[Documentation Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

## DuckDNS depuis le contrôleur externe

Copier [l'exemple du contrôleur](../deploy/oracle/controller.env.example) dans
un coffre ou fichier privé **hors de la VM**. Le moteur Python n'a pas besoin
du jeton DuckDNS. Après création ou reconstruction, le contrôleur doit lire
l'IP publique effective dans Oracle puis exécuter :

```sh
python -m scripts.update_oracle_dns --env-file CHEMIN_PRIVE --ipv4 IP_PUBLIQUE_ORACLE
```

L'IPv4 est obligatoire et ne peut pas être une adresse privée. Le script ne
laisse jamais DuckDNS détecter l'IP du contrôleur. Il vérifie la réponse du
fournisseur, masque le jeton dans ses erreurs et ne considère pas une réponse
`OK` comme une preuve de propagation DNS ou de disponibilité HTTPS.
[Spécification DuckDNS](https://www.duckdns.org/spec.jsp).

La première version utilise un enregistrement A IPv4 ; ne pas conserver un
enregistrement AAAA vers une ancienne VM. Après mise à jour, le futur contrôleur
devra attendre la résolution correcte, puis vérifier HTTPS et `/ready` avant
d'annoncer le monde disponible. La reconstruction OCI, son verrouillage et
ces vérifications coordonnées ne sont pas encore implémentés. Le script DNS
est le point d'intégration prévu et n'a pas été appelé avec un jeton réel.

Le domaine `jeux-rpg.duckdns.org` a depuis été ajouté au compte DuckDNS par le
propriétaire. Sur le poste, le jeton est fourni par `DUCKDNS_TOKEN` dans `.env`,
hors Git. Le script accepte aussi ce nom ; `RPG_DUCKDNS_TOKEN` reste prioritaire
lorsque les deux sont présents. Pour utiliser ce fichier lors de la future
mise à jour, ajouter `--env-file .env` à la commande. L'IP Oracle reste
obligatoire : le jeton local n'entraîne aucune mise à jour DNS automatique.

## Arrêt et redémarrage sûrs

Le service lance `jeuxRPG.multiplayer.host`, un seul worker Uvicorn, derrière
Caddy. Il annonce son démarrage à systemd après le chargement D1 et envoie un
signal de vie au watchdog. Un crash peut provoquer un redémarrage ; les données
non sauvegardées au moment d'un crash peuvent toujours être perdues.

Sur SIGTERM ou SIGINT, le processus passe en drainage : il refuse les nouvelles
mutations et suspend la simulation, capture le dernier lot puis exige une
confirmation D1. Si D1 échoue, il conserve sa RAM et réessaie ; `/ready` renvoie
503. Les signaux répétés ne forcent pas sa fermeture. Après confirmation, les
sockets sont fermées et le processus quitte normalement. Un moteur déjà
remplacé par une nouvelle génération se retire sans tenter d'écrire son ancien
état ; il ne redémarre pas automatiquement pour reprendre la propriété.

`TimeoutStopSec=infinity` et `SendSIGKILL=no` évitent que le stop normal systemd
interrompe cette attente. Un déploiement peut donc rester en attente pendant
une panne D1. Une coupure de la VM, une terminaison externe ou un crash restent
possibles ; cette configuration ne protège pas la RAM contre ces événements.
[Référence systemd](https://www.freedesktop.org/software/systemd/man/255/systemd.service.html).

Le futur arrêt après une heure d'inactivité devra utiliser ce drainage, avec
son propre contrôle des activations concurrentes. Il n'est pas activé par le
timer de maintenance. L'arrêt VM cinq heures plus tard et le réveil externe
restent des étapes séparées.

## Automatisation préparée

| Automatisation | Déclenchement et comportement |
| --- | --- |
| Validation du kit | PR touchant les fichiers concernés, ou lancement manuel : tests, Bash, cloud-init, Caddy et systemd |
| Déploiement VM | Workflow manuel `oracle-preview.yml`, après validation, avec `deploy=true` et `ORACLE_DEPLOY_ENABLED=true` |
| Mise à jour DNS | Après déploiement si `ORACLE_DUCKDNS_ENABLED=true` ; même commande réutilisable par le futur contrôleur de reconstruction |
| Maintenance de l'hôte | Dimanche à 06h00 Europe/Paris, décalage aléatoire jusqu'à 30 min ; santé, disque, journaux et liste des mises à jour disponibles |
| Sauvegarde indépendante | Workflow `oracle-operations.yml`, chaque jour à 04h35 Europe/Paris, si `ORACLE_AUTOMATION_ENABLED=true` |
| Surveillance externe | Dans le même workflow quotidien, si l'URL est configurée ; aucun réveil ni arrêt de VM déclenché |

La maintenance n'installe pas automatiquement les mises à jour et ne redémarre
pas l'OS. La surveillance quotidienne ne remplace pas un contrôleur de réveil
ou une alerte rapide sur indisponibilité.

La sauvegarde est exportée depuis D1 en lecture seule, restaurée et vérifiée
avec les outils existants, puis chiffrée avec `age`. Seuls le fichier chiffré,
son checksum et le rapport de vérification sont téléversés dans un artefact
GitHub conservé 14 jours, indépendamment du disque Oracle. La clé privée de
déchiffrement reste chez le propriétaire. Cela conserve D1 et son protocole de
sauvegarde ; le nouveau workflow utilise uniquement la base fictive tant que
la bascule de production n'a pas été réalisée.

Créer l'environnement GitHub `oracle-preview` avant activation :

| Configuration | Emplacement |
| --- | --- |
| `ORACLE_DEPLOY_ENABLED`, `ORACLE_AUTOMATION_ENABLED` | Variables du dépôt, absentes ou `false` tant que l'hôte n'est pas prêt |
| `ORACLE_SSH_HOST`, `ORACLE_SSH_USER` | Variables de l'environnement `oracle-preview` |
| `ORACLE_SSH_KEY`, `ORACLE_SSH_KNOWN_HOSTS` | Secrets de cet environnement ; empreinte SSH vérifiée indépendamment, sans acceptation automatique |
| `RPG_D1_SERVICE_TOKEN` | Secret du Worker fictif dans cet environnement |
| `RPG_BACKUP_RECIPIENT` | Clé publique `age`, variable d'environnement GitHub |
| `ORACLE_ENGINE_URL` | Variable du dépôt : `https://jeux-rpg.duckdns.org` |
| `ORACLE_DUCKDNS_ENABLED`, `ORACLE_PUBLIC_IPV4` | Variables de l'environnement : activation et IP publique effective Oracle |
| `RPG_DUCKDNS_TOKEN` | Secret de cet environnement, pour la commande DNS extérieure à la VM |

Les runners GitHub doivent avoir un accès SSH autorisé par les règles réseau
OCI. Les workflows ne configurent pas ces règles. Les tâches planifiées ne
s'exécutent qu'une fois le workflow présent sur la branche par défaut et son
activation configurée. [Planification GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).

## Validation et limites actuelles

Les tests couvrent un serveur HTTP réel : gestionnaire SIGTERM pendant une panne D1 simulée,
RAM et personnage conservés, refus de nouvelles mutations, signaux répétés,
puis sauvegarde et sortie après rétablissement. Les tests DNS ne contactent pas
DuckDNS et vérifient notamment l'IP explicite et la confidentialité du jeton.
Le cloud-init, les unités et la configuration Caddy sont vérifiés avec les
validateurs Linux ; les scripts Bash et workflows sont contrôlés par ShellCheck
et actionlint.

Une [recette ciblée du drainage avec le D1 distant fictif](oracle-test-20261113/host-shutdown.json)
confirme aussi la conservation d'une progression en RAM pendant l'échec injecté,
la sortie après confirmation et la restauration depuis D1. Le gestionnaire de
signal est appelé directement dans cette recette ; ce n'est pas un essai de
`systemctl stop` sur une VM. Les données fictives ont été nettoyées.

Les validateurs utilisés localement sont cloud-init 26.1, systemd 259,
Caddy 2.6.2, ShellCheck 0.11.0 et actionlint 1.7.12 sous Ubuntu WSL x86_64.
La suite ciblée moteur/comptes/sauvegardes a terminé avec 83 tests réussis et
un test ignoré ; les nouveaux tests du kit et du DNS passent également.

La VM ARM64, le certificat réel, le déploiement SSH et l'exécution des nouveaux
workflows sur GitHub restent à vérifier après création des comptes et mise à
disposition de l'hôte. Le [test de 40 sockets déjà réalisé](oracle-test-20261113/REPORT.md)
utilise toujours le moteur local et D1 distant, pas une VM Oracle.
