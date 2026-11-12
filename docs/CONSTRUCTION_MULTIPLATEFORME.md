# Construire Windows, Linux et Android

Depuis Windows : `build-distribution.cmd`. Prérequis : Python 3.11+, Node.js 22.12+, dépendances `npm ci --prefix desktop`, et WSL Ubuntu installé. La commande exporte le contenu du Builder une fois puis construit les trois clients dans `dist/windows`, `dist/linux` et `dist/mobile`.

Les outils Linux/Android sont téléchargés et vérifiés dans `.toolchains` : Node, JDK, Gradle, Android SDK. Les versions de Node/Gradle/SDK sont fixées dans les scripts ; les URL et empreintes de téléchargement sont enregistrées dans `.toolchains/platform-tools.json` et `.toolchains/android-packages.json`. Aucun envoi vers une boutique ou un hébergeur n'est effectué.

Étapes séparées après préparation des ressources par `node desktop/build.cjs --prepare-only` :

```powershell
python scripts/prepare_platform_toolchains.py
wsl -d Ubuntu -- bash /mnt/c/save/perso/projet/jeuxRPG/scripts/build-linux.sh
python scripts/install_android_sdk.py
python scripts/prepare_android_client.py
wsl -d Ubuntu -- bash /mnt/c/save/perso/projet/jeuxRPG/scripts/build-android.sh
python scripts/build_distribution.py --finalize-only
```

Adapter le chemin WSL si le dépôt est déplacé. Le script d'orchestration le calcule automatiquement.

## Signature Android

La première préparation crée `.signing/android/signing.properties` ; la première construction génère `.signing/android/jeux-rpg.jks`. Ces fichiers sont ignorés par Git. Conserver une sauvegarde privée de ce dossier : les futures versions doivent utiliser la même clé pour mettre à jour l'application installée sans désinstallation. Ne pas distribuer ce dossier avec les exécutables.

La version distribuée est une version release signée, sans débogage WebView. Un APK debug séparé, de nom de paquet distinct, est produit dans `android/app/build/outputs/apk/debug` pour les essais.

## Hôte Android

Le WebView charge les ressources embarquées via [WebViewAssetLoader](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content) sur une origine HTTPS locale. Le worker Pyodide, son interpréteur Python et l'export du Builder sont embarqués. IndexedDB conserve les sauvegardes. Aucun serveur local ni installation Python sur le téléphone n'est nécessaire.

Le pont natif traite les requêtes API du document principal vers le seul serveur HTTPS du manifeste. Le client mobile utilise le repli HTTP du jeu pour le multijoueur. Les ressources externes, l'accès aux fichiers et les permissions WebView sont refusés.

## Vérification

`wsl -d Ubuntu -- bash <chemin-du-dépôt>/scripts/verify-linux.sh` vérifie le client Linux compilé avec réseau bloqué : entrée solo, création du personnage, démarrage du jeu, sauvegarde et reprise après fermeture. Les options Chromium sans bac à sable et sans affichage concernent uniquement ce test automatisé.

`build-android.sh` vérifie la signature de l'APK avec `apksigner`. Le contenu embarqué et son manifeste doivent être contrôlés après chaque préparation. Pour tester sur appareil : installer l'APK debug avec `adb install -r`, ouvrir `fr.jeuxrpg.mobile.debug/fr.jeuxrpg.mobile.MainActivity`, puis utiliser l'inspection WebView.

Pour installer aussi l'émulateur de test, passer `--with-emulator` à `scripts/install_android_sdk.py`. L'installation native Windows évite les déplacements de milliers de petits fichiers à travers WSL. Les archives officielles du SDK sont vérifiées avant extraction. `start-android-emulator.sh` démarre l'appareil virtuel sans fenêtre, avec ses données dans `.data`. Sous WSL, utiliser un utilisateur ayant accès à `/dev/kvm`. Lancer ensuite dans WSL, avec le Node Linux préparé, `scripts/verify_android.cjs` : ce test réinitialise uniquement le paquet debug, coupe le réseau et vérifie la création, le démarrage solo, la reprise après arrêt forcé et le bouton Retour natif. Exemple depuis Windows :

```powershell
wsl -d Ubuntu -u root -- /mnt/c/save/perso/projet/jeuxRPG/.toolchains/node/bin/node /mnt/c/save/perso/projet/jeuxRPG/scripts/verify_android.cjs
```

Gradle utilise un cache temporaire Linux sous `/tmp/jeux-rpg-gradle-<uid>`, afin d'éviter les erreurs de renommage atomique sur le disque Windows. La variable `RPG_GRADLE_CACHE` permet de choisir un autre répertoire Linux. Le SDK, les clés de signature et les exécutables restent dans le dépôt.

## Validation de cette distribution — 12 novembre 2026

- Linux x86_64 : client compilé démarré sous Ubuntu/WSL, réseau bloqué, personnage créé, solo démarré, fermeture et reprise de sauvegarde réussies.
- Android : APK debug installé dans un émulateur Android 15, WebView Chromium 124, Wi-Fi et données désactivés. Création, démarrage solo, reprise après arrêt forcé, fermeture du journal puis sortie avec Retour Android réussies. Capture : `.data/android-offline.png`.
- APK release : signature v2 vérifiée par `apksigner`, paquet `fr.jeuxrpg.mobile`, version `0.11.0`, Android minimum 29 et cible 35. Empreintes de tous les fichiers web vérifiées dans l'APK ; interpréteur WASM, bibliothèque Python et moteur Builder présents.
- Windows : exécutable portable précédemment validé, conservé dans `dist/client` et copié à l'identique dans `dist/windows`.

Les essais Android utilisent le même hôte et les mêmes ressources en variante debug, avec un nom de paquet distinct. La variante release distribuée désactive le débogage du WebView. Aucun téléphone physique n'a été utilisé pour cette validation.
