# Jeux RPG — Windows, Linux et Android

Les trois versions embarquent le même contenu du Builder, l'histoire, les dialogues et les quêtes. Le mode solo fonctionne sans connexion. Les sauvegardes solo restent sur chaque appareil ; elles ne sont pas partagées entre plateformes. Le multijoueur nécessite une connexion au serveur.

## Windows 64 bits

Lancer `windows/Jeux-RPG.exe`. La copie historique `client/Jeux-RPG.exe` est conservée pour les raccourcis existants. Garder le même compte Windows pour retrouver la sauvegarde.

## Linux 64 bits (x86_64)

Rendre `linux/Jeux-RPG-Linux-x86_64.AppImage` exécutable dans ses propriétés, puis l'ouvrir. En terminal :

```sh
chmod +x Jeux-RPG-Linux-x86_64.AppImage
./Jeux-RPG-Linux-x86_64.AppImage
```

Si FUSE n'est pas disponible, lancer `./Jeux-RPG-Linux-x86_64.AppImage --appimage-extract-and-run`, ou extraire `Jeux-RPG-Linux-x64.tar.gz` et lancer `jeux-rpg`. Utiliser une distribution Linux de bureau récente avec les bibliothèques GTK/NSS usuelles. Conserver les fichiers extraits ensemble.

## Android — APK

Copier `mobile/Jeux-RPG-Android.apk` sur l'appareil puis ouvrir le fichier. Autoriser l'installation depuis l'application utilisée pour ouvrir cet APK si Android le demande. Android 10 ou plus récent et Android System WebView à jour sont requis. L'APK est universel et ne nécessite pas Google Play pour jouer en solo.

Le bouton Retour ferme d'abord le dialogue ou le menu ouvert. Sinon il sauvegarde le solo et quitte l'application. Les actions solo réussies sont aussi sauvegardées automatiquement. Une mise à jour avec le même APK signé conserve les données ; désinstaller l'application les efface.

`SHA256SUMS.txt` fournit les empreintes des fichiers distribués.
