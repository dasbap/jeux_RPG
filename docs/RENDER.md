# Recette Render Free

Oracle est abandonné faute de capacité. Northflank n'a reçu aucun secret du projet.
La recette choisie utilise un seul moteur Python sur Render Free et le D1 fictif
existant. Vercel et les données de production restent inchangés.

## Installation

1. Connecter Render au profil GitHub qui possède `dasbap/jeux_RPG`.
2. Utiliser la branche `migration/render-single-d1` et son `render.yaml`.
   Le Blueprint prévoit uniquement un service web **Free** à Francfort, sans
   base Render, disque, Redis ni autre ressource payante.
3. Fournir le jeton du Worker D1 isolé en variable secrète de runtime
   `RPG_D1_SERVICE_TOKEN`. Le secret existe localement dans le fichier ignoré
   `.data/oracle-test/runtime.env` ; ne jamais l'afficher ni le mettre dans Git.
   Le nom historique du Worker ne désigne pas une ressource Oracle.
4. Render génère `RPG_ADMIN_TOKEN`. Le moteur déduit son origine HTTPS de
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

Le fichier créé `.data/render/runtime.env` est ignoré par Git. La commande refuse
un remplacement de fichier, une autre base ou un domaine hors Render. Elle
vérifie D1 en lecture seule, sans prendre possession du moteur.

## Automatisation

- `render-preview.yml` vérifie le moteur et construit le Dockerfile dans GitHub
  Actions. Aucun secret D1 n'entre dans l'image. Le contexte Docker exclut les
  fichiers privés, les sauvegardes et les dossiers de travail.
- `render-operations.yml` prépare une sauvegarde D1 quotidienne à 04:35 Europe/Paris,
  indépendante du moteur, restaurée pour contrôle et chiffrée avec `age` avant
  stockage en artifact pendant 14 jours. Elle exige la variable GitHub
  `RENDER_AUTOMATION_ENABLED=true`, l'environnement `render-preview`, le secret
  `RPG_D1_SERVICE_TOKEN` et la clé publique `RPG_BACKUP_RECIPIENT`.
  Les déclenchements planifiés exigent que le workflow existe sur la branche
  par défaut. Les workflows locaux ne sont pas encore exécutés.
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
Sans moyen de paiement, les dépassements entraînent une suspension plutôt qu'un
achat automatique ; ne pas passer à un plan payant pour contourner une limite.

Sources officielles : [Free](https://render.com/docs/free),
[ressources](https://render.com/docs/compute-plans),
[WebSockets](https://render.com/docs/websocket),
[Blueprint](https://render.com/docs/blueprint-spec).
