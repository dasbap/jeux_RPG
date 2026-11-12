# Client Windows

Le client Windows embarque le même HTML, CSS et JavaScript que le site, ainsi que
le moteur Python et Pyodide. Le mode **Solo** fonctionne sans connexion, dès le
premier lancement. Le mode **En ligne** utilise les comptes et parties du serveur
`https://jeux-rpg.vercel.app`.

## Construire en une commande

Depuis la racine du dépôt, sous Windows 10/11 x64 :

```powershell
.\build-client.cmd
```

Prérequis de construction : **Node.js 22.12 ou plus récent** et **Python 3.11 ou
plus récent**, accessibles dans le terminal. La commande installe les outils
verrouillés dans `desktop/package-lock.json`, régénère le client à partir de
`jeuxRPG/multiplayer/web` et construit :

```text
dist/client/Jeux-RPG.exe
```

Ce fichier est portable : copier uniquement ce `.exe` sur un autre PC Windows x64.
Le joueur n'a besoin ni de Python, ni de Node.js, ni d'une base de données locale
à installer. Internet est nécessaire à la construction et au multijoueur, pas au
solo. L'exécutable n'est pas signé avec un certificat d'éditeur.

Après une modification du client web, relancer la même commande. La construction
est un instantané des sources locales : elle ne télécharge pas automatiquement
une autre branche et ne modifie pas le site publié.

## Sauvegardes et mises à jour

Les sauvegardes solo sont stockées dans le profil Windows
`%APPDATA%\JeuxRPG`, dans IndexedDB. La fermeture normale attend la sauvegarde du
moteur. Remplacer ou déplacer le `.exe` conserve ce profil et la progression.
Pour sauvegarder manuellement le profil, fermer l'application puis copier ce
dossier.

Le navigateur et l'application ont des profils séparés : une sauvegarde solo du
site n'est pas automatiquement transférée. Les comptes multijoueurs restent les
mêmes sur les deux clients. Aucun secret D1, Cloudflare ou Vercel n'est embarqué.

## Développement et vérification

Après `npm --prefix desktop ci`, lancer le client avec :

```powershell
npm --prefix desktop start
```

Le menu propose le plein écran, le rechargement et les outils de diagnostic.
Les outils Node restent désactivés dans la page du jeu et son Worker.

Contrôles automatisés :

```powershell
npm --prefix desktop test
npm install --prefix .ui-test playwright@1.56.1
node scripts/verify_desktop.cjs
node scripts/verify_desktop.cjs --packaged
```

Le dernier contrôle nécessite une construction préalable. Il lance le véritable
client compilé, bloque HTTP/HTTPS/WebSocket, crée une partie solo, ferme
l'application puis vérifie la reprise au redémarrage dans un profil de test.

Le workflow GitHub Actions **Client Windows** fournit aussi le `.exe` comme
artefact et peut être lancé manuellement. `desktop/assets` et `dist` sont générés
et exclus de Git ; les sources, les scripts et le verrou des dépendances sont
versionnés.

La construction valide puis exporte le projet `projects/authored` vers
`jeuxRPG/maps` avant de préparer le moteur solo. Le catalogue livré correspond
donc au projet Builder courant. Pour exporter aussi les catalogues utilisés par
le serveur, exécuter `python -m scripts.export_builder_project`, puis déployer
le serveur avec ces fichiers.
