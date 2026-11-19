# Construire Windows, Linux et Android

Le seul prérequis sur l’hôte est Docker avec un moteur de conteneurs Linux et
l’émulation `linux/amd64` sur les machines ARM. Depuis Windows :

```powershell
.\build-client.cmd                 # Windows uniquement
.\build-distribution.cmd linux     # Linux uniquement
.\build-distribution.cmd android   # Android uniquement
.\build-distribution.cmd           # Les trois plateformes
```

Sous Linux/macOS : `bash scripts/build-docker.sh windows|linux|android|all`
(sans argument : `all`). Les chemins sont calculés depuis la position du script.

`deploy/build/Dockerfile` définit deux images : `desktop` (Windows/Linux avec
Wine) et `android` (JDK 17, Gradle et SDK en plus). L’image Node est verrouillée
par digest ; les dépendances npm viennent de `desktop/package-lock.json` et les
archives Gradle/SDK de `deploy/build/tools.lock.json`, avec contrôle d’empreinte.
Les paquets Debian sont installés dans le conteneur. Cette isolation ne garantit
pas des exécutables identiques octet par octet : les dépôts Debian et certains
outils d’empaquetage peuvent évoluer.

Le premier build télécharge les images et dépendances officielles. Les ressources
du jeu proviennent exclusivement de `jeuxRPG/` et `projects/authored/` copiés
depuis le dépôt ; aucun outil, catalogue, cache, profil ou `node_modules` de l’hôte
n’est importé. Le contexte Docker utilise une liste autorisée propre à ce build,
sans modifier le contexte de l’hébergement Render. Les assets et le moteur solo
sont préparés dans l’image. Le répertoire source de l’hôte n’est pas monté dans
le conteneur d’exécution.

Seuls `dist/` et, pour Android, `.signing/` sont montés. Le conteneur construit
d’abord dans son propre système de fichiers, puis exporte les livrables dans
`dist/windows`, `dist/linux`, `dist/mobile` et met à jour `artifacts.json` et
`SHA256SUMS.txt`. Le portable Windows est également copié dans `dist/client`.
Les empreintes des anciennes plateformes encore présentes sont conservées ;
seule la cible demandée est reconstruite. Aucune publication n’est effectuée.

Une fois les images préparées, leur exécution directe est possible :

```powershell
docker run --rm --mount "type=bind,source=${PWD}/dist,target=/out" jeux-rpg-build:desktop windows
```

Le build natif historique (`node desktop/build.cjs`, scripts WSL) reste disponible
pour le développement. Il n’est pas appelé par les lanceurs de livraison Docker.

## Signature Android

La première préparation crée `.signing/android/signing.properties` ; la première construction génère `.signing/android/jeux-rpg.jks`. Ces fichiers sont ignorés par Git. Conserver une sauvegarde privée de ce dossier : les futures versions doivent utiliser la même clé pour mettre à jour l'application installée sans désinstallation. Ne pas distribuer ce dossier avec les exécutables.

La version distribuée par Docker est une version release signée, sans débogage
WebView. Le script natif historique `build-android.sh` produit aussi un APK debug
séparé, de nom de paquet distinct, pour les essais sur émulateur.

## Hôte Android

Le WebView charge les ressources embarquées via [WebViewAssetLoader](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content) sur une origine HTTPS locale. Le worker Pyodide, son interpréteur Python et l'export du Builder sont embarqués. IndexedDB conserve les sauvegardes. Aucun serveur local ni installation Python sur le téléphone n'est nécessaire.

Le pont natif traite les requêtes API du document principal vers le seul serveur HTTPS du manifeste. Le client mobile utilise le repli HTTP du jeu pour le multijoueur. Les ressources externes, l'accès aux fichiers et les permissions WebView sont refusés.

## Vérification

`node scripts/verify_portable_windows.cjs` teste le portable Windows exact avec
un profil temporaire : création solo, scène 3D, disparition de la barre, centrage
du dialogue dès la première image, fermeture normale et reprise du personnage.
Ce test utilise Node et Playwright sur Windows ; il est séparé du build Docker.
Le workflow `client-windows.yml` construit avec Docker sur Linux et transfère le
portable à un job Windows pour cette validation, sans le reconstruire.

Le conteneur Android vérifie la signature release avec `apksigner` avant export.
Les commandes WSL ci-dessous concernent les parcours de développement natifs et
les essais sur émulateur, indépendants du nouveau build Docker.

`wsl -d Ubuntu -- bash <chemin-du-dépôt>/scripts/verify-linux.sh` vérifie le client Linux compilé avec réseau bloqué : entrée solo, création du personnage, démarrage du jeu, sauvegarde et reprise après fermeture. Les options Chromium sans bac à sable et sans affichage concernent uniquement ce test automatisé.

`build-android.sh` vérifie la signature de l'APK avec `apksigner`. Le contenu embarqué et son manifeste doivent être contrôlés après chaque préparation. Pour tester sur appareil : installer l'APK debug avec `adb install -r`, ouvrir `fr.jeuxrpg.mobile.debug/fr.jeuxrpg.mobile.MainActivity`, puis utiliser l'inspection WebView.

Pour installer aussi l'émulateur de test, passer `--with-emulator` à `scripts/install_android_sdk.py`. L'installation native Windows évite les déplacements de milliers de petits fichiers à travers WSL. Les archives officielles du SDK sont vérifiées avant extraction. `start-android-emulator.sh` démarre l'appareil virtuel sans fenêtre, avec ses données dans `.data`. Sous WSL, utiliser un utilisateur ayant accès à `/dev/kvm`. Lancer ensuite dans WSL, avec le Node Linux préparé, `scripts/verify_android.cjs` : ce test réinitialise uniquement le paquet debug, coupe le réseau et vérifie la création, le démarrage solo, la reprise après arrêt forcé et le bouton Retour natif. Exemple depuis Windows :

```powershell
wsl -d Ubuntu -u root -- /mnt/c/save/perso/projet/jeuxRPG/.toolchains/node/bin/node /mnt/c/save/perso/projet/jeuxRPG/scripts/verify_android.cjs
```

Gradle utilise un cache temporaire Linux sous `/tmp/jeux-rpg-gradle-<uid>`, afin d'éviter les erreurs de renommage atomique sur le disque Windows. La variable `RPG_GRADLE_CACHE` permet de choisir un autre répertoire Linux. Le SDK, les clés de signature et les exécutables restent dans le dépôt.

## Validation Docker — 18 novembre 2026

- Windows : portable construit par `build-client.cmd` dans Docker, puis testé
  sous Windows avec création solo hors ligne, scène WebGL, barre masquée,
  dialogue centré dès la première image et personnage conservé après fermeture
  et redémarrage.
- Linux : AppImage et archive construits dans Docker ; exécutable de l’archive
  testé dans un conteneur sans écran avec SwiftShader pour la même séquence
  solo, interface et reprise. L’AppImage n’a pas été lancée séparément.
- Android : release construite avec le SDK et Gradle téléchargés selon le verrou
  du dépôt ; clé existante conservée, signature v2 vérifiée, empreintes de toutes
  les ressources web dans l’APK conformes au manifeste. Aucun nouvel essai sur
  appareil ou émulateur n’a été réalisé pour cette reconstruction.
- Empreintes des quatre livrables et identité des copies Windows vérifiées.
  Le contexte de l’image ne contient ni `.env`, `.git`, sauvegardes, clés ni
  environnements Python de l’hôte.
- Contrôles du checkpoint : 176 tests Python ciblant les fichiers de test
  modifiés/ajoutés, 54 tests JavaScript et les trois tests du runtime dans l’image
  réussis. Les scripts de build ajoutés passent Ruff. Le contrôle Ruff étendu
  conserve 16 erreurs dans des fichiers de test antérieurement modifiés.

## Validation historique — 12 novembre 2026

- Linux x86_64 : client compilé démarré sous Ubuntu/WSL, réseau bloqué, personnage créé, solo démarré, fermeture et reprise de sauvegarde réussies.
- Android : APK debug installé dans un émulateur Android 15, WebView Chromium 124, Wi-Fi et données désactivés. Création, démarrage solo, reprise après arrêt forcé, fermeture du journal puis sortie avec Retour Android réussies. Capture : `.data/android-offline.png`.
- APK release : signature v2 vérifiée par `apksigner`, paquet `fr.jeuxrpg.mobile`, version `0.11.0`, Android minimum 29 et cible 35. Empreintes de tous les fichiers web vérifiées dans l'APK ; interpréteur WASM, bibliothèque Python et moteur Builder présents.
- Windows : exécutable portable précédemment validé, conservé dans `dist/client` et copié à l'identique dans `dist/windows`.

Les essais Android utilisent le même hôte et les mêmes ressources en variante debug, avec un nom de paquet distinct. La variante release distribuée désactive le débogage du WebView. Aucun téléphone physique n'a été utilisé pour cette validation.
