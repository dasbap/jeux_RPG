# Recette Render Free

Oracle est abandonné faute de capacité. Northflank n'a reçu aucun secret du projet.
La recette choisie utilise un seul moteur Python sur Render Free et le D1 fictif
existant. Vercel et les données de production restent inchangés.

Le service `jeux-rpg-render-test` est déployé à Francfort depuis le 14 novembre
2026 : [jouer sur la recette](https://jeux-rpg-render-test.onrender.com),
[tableau de bord](https://dashboard.render.com/web/srv-dbrq9rei0phs73b65dag).
Le parcours navigateur a confirmé compte, personnage, aventure et WebSocket,
sans erreur JavaScript ni réponse serveur 5xx. Une lecture indépendante du D1
isolé a confirmé la sauvegarde du compte, du personnage et de l'aventure.
Le [rapport de recette](render-test-20261114/REPORT.md) détaille la charge
progressive, les latences trop élevées à 40 joueurs et la reprise après
redémarrage avec 41 comptes, personnages et aventures conservés.

## Installation

1. Connecter Render au profil GitHub qui possède `dasbap/jeux_RPG`.
2. Utiliser la branche `migration/render-single-d1` et son `render.yaml`.
   Le Blueprint prévoit uniquement un service web **Free** à Francfort, sans
   base Render, disque, Redis ni autre ressource payante.
3. Ajouter dans **Secret Files** un fichier `rpg-runtime.json` contenant uniquement
   `RPG_D1_SERVICE_TOKEN` et `RPG_ADMIN_TOKEN` au format JSON. Le jeton D1
   existe localement dans le fichier ignoré
   `.data/oracle-test/runtime.env` ; ne jamais l'afficher ni le mettre dans Git.
   Le nom historique du Worker ne désigne pas une ressource Oracle.
4. Le moteur lit les jetons depuis `/etc/secrets/rpg-runtime.json`, sans les
   inclure dans l'image Docker. Il déduit son origine HTTPS de
   `RENDER_EXTERNAL_HOSTNAME`, écoute sur `PORT` et sert directement l'interface
   de test sur son adresse `onrender.com`. Le site Vercel n'est pas encore relié
   au nouveau moteur.
5. Vérifier `/ready`, créer un compte fictif puis jouer et reconnecter le
   WebSocket après redémarrage. Tester progressivement 1, 10 puis 40 joueurs,
   en observant CPU, RAM, trafic et sauvegardes D1.

Pour un import manuel des variables, après attribution de l'adresse :

```powershell
.venv-reprise/Scripts/python.exe -m scripts.prepare_render_preview --origin https://ADRESSE.onrender.com
```

Les fichiers créés sont ignorés par Git : `runtime-public.env` pour les réglages
ordinaires et `rpg-runtime.json` pour la rubrique **Secret Files**. Le fichier
local `runtime.env` conserve les valeurs d'origine ; ne pas l'importer parmi
les variables ordinaires. La commande refuse un remplacement de fichier, une
autre base ou un domaine hors Render. Elle vérifie D1 en lecture seule, sans
prendre possession du moteur.

## Automatisation

- `render-preview.yml` vérifie le moteur et construit le Dockerfile dans GitHub
  Actions. Aucun secret D1 n'entre dans l'image. Le contexte Docker exclut les
  fichiers privés, les sauvegardes et les dossiers de travail.
- `render-operations.yml` prépare une sauvegarde D1 quotidienne à 04:35 Europe/Paris,
  indépendante du moteur, restaurée pour contrôle et chiffrée avec `age` avant
  stockage en artifact pendant 14 jours. Elle exige la variable GitHub
  `RENDER_AUTOMATION_ENABLED=true`, l'environnement `render-preview`, le secret
  GitHub Actions `RENDER_TEST_D1_SERVICE_TOKEN` et la clé publique
  `RPG_BACKUP_RECIPIENT`. Ces paramètres de test sont configurés.
  Les déclenchements planifiés exigent que le workflow existe sur la branche
  par défaut. La construction de l'image et les tests ont réussi sur GitHub
  Actions. La sauvegarde manuelle a réussi : export de 41 comptes, restauration
  contrôlée, réouverture du moteur, chiffrement `age` et artifact dont la somme
  de contrôle a été vérifiée après téléchargement. Le planificateur quotidien
  attend l'intégration dans la branche par défaut.
  Pour lancer sa recette depuis la branche de migration, le workflow
  `render-preview.yml` accepte un déclenchement manuel avec `backup=true`.
- Les redéploiements automatiques sont désactivés pour la recette. Le fencing
  protège contre les écritures d'un ancien moteur, mais ne transfère pas les
  changements RAM encore non sauvegardés. Un remplacement contrôlé doit donc
  confirmer la sauvegarde avant de lancer le nouveau moteur. L'automatisation
  de cette bascule reste à réaliser avant un usage de production.
- Aucun contrôleur Oracle, DNS dynamique, Caddy ou ping de maintien en activité.

## Limites acceptées pour le test

Render Free dispose de 0,1 CPU et 512 Mo de RAM. Les 40 joueurs ne sont pas
validés sur ces ressources. Le service dort après 15 minutes sans trafic entrant
et se réveille à la prochaine requête, normalement en environ une minute.
Les 750 heures gratuites sont partagées dans le workspace.

Les fichiers locaux sont éphémères. D1 reste la source durable ; les mises à jour
non sauvegardées peuvent être perdues lors d'un arrêt forcé. Le moteur tente la
sauvegarde finale après SIGTERM, mais Render peut envoyer SIGKILL après le délai
imposé : le Blueprint demande 300 secondes, sans garantie en cas de panne.
Le contrôle de santé utilise `/health`, et non `/ready`, pour éviter qu'une panne
D1 temporaire déclenche un redémarrage qui détruirait des changements en RAM.

Le trafic WebSocket sortant compte dans le quota réseau. Render peut également
suspendre un service gratuit qui appelle excessivement une base externe.
L'interface Render réserve ses graphiques CPU et mémoire aux instances payantes ;
la recette Free ne permet donc pas de conclure sur leur marge à partir de ces
graphiques. Les tailles reçues mesurées par les sondes sont des octets applicatifs,
pas une mesure de bande passante facturée après compression.
Sans moyen de paiement, les dépassements entraînent une suspension plutôt qu'un
achat automatique ; ne pas passer à un plan payant pour contourner une limite.

Sources officielles : [Free](https://render.com/docs/free),
[ressources](https://render.com/docs/compute-plans),
[WebSockets](https://render.com/docs/websocket),
[Blueprint](https://render.com/docs/blueprint-spec).
