# Préproduction D1 — 6 novembre 2026

## Réalisé

La base initiale `jeux-rpg-preview` a été créée avec `--jurisdiction eu` pour
les essais fictifs. Après autorisation, une nouvelle base européenne vide
`jeux-rpg-import-preview` a été créée pour l'import réel. Son identifiant et le
binding `DB` sont maintenant dans `cloudflare/wrangler.preview.json`. Le schéma
du jeu (version 3) et les deux triggers de protection du moteur sont installés.

Le Worker authentifié est publié à
`https://jeux-rpg-d1-preview.dasbap-jeux-rpg.workers.dev`.
Sans authentification, il renvoie HTTP 401. Le secret de préproduction est dans
`.data/d1-migration/preview.env`, ignoré par Git et placé dans un dossier Windows
dont les droits sont restreints à l'utilisateur courant.

La recette réelle `scripts/verify_d1_preview.py` a validé :

- création d'un compte fictif, personnage et tutoriel ;
- sauvegarde puis reconstruction d'un moteur depuis D1 ;
- reconnexion avec le mot de passe et reprise de la session ;
- refus du moteur périmé lors de sauvegardes concurrentes ;
- annulation complète d'un lot avec une clé étrangère invalide.

Les données fictives ont été retirées de la base initiale. Le Worker de
préproduction est maintenant lié à la nouvelle base importée. Ne pas relancer
`verify_d1_preview.py` sur ces données : le script refuse une base non vide.
Le contrôle d'import `verify_d1_import.py` reste intégralement en lecture seule.

## Retrait progressif de Turso

Avec `RPG_DATABASE_BACKEND=d1`, le moteur utilise exclusivement le client D1.
Une panne ne déclenche aucune écriture de secours dans Turso. Un accès au serveur
WSGI historique est refusé dans ce mode : l'entrée du jeu reste `app:app` en ASGI.

Le build et les contrôles de stockage choisissent leurs variables selon le backend.
`prepare_vercel_environment` retire les variables Turso de la configuration locale
du build D1. La coordination Redis D1 utilise un préfixe dérivé de l'URL du Worker,
différent de celui de Turso et des autres bases D1.

`scripts/export_database_backup.py` prépare une sauvegarde SQLite privée du
stockage sélectionné ; `scripts/check_database.py` contrôle son schéma et ses
relations. Le code Turso reste disponible pour l'export initial et le retour arrière.
Le workflow de publication sélectionne désormais le backend pour la sauvegarde,
sa restauration de contrôle, la vérification et la synchronisation des accès.
Il ne dépend plus obligatoirement de Turso. L'administration utilise également
un script commun en lecture seule. Les sauvegardes de publication restent
chiffrées et conservées trente jours. Aucune publication de production n'est
exécutée lors de cette étape et son backend n'est pas basculé.

## Export autorisé et exécuté

La PR [#90](https://github.com/dasbap/jeux_RPG/pull/90), fusionnée, prépare un export Turso
en lecture seule, chiffré avec age et conservé sept jours dans un artefact GitHub.
Tous ses contrôles GitHub sont verts. La clé privée est conservée uniquement sur
le poste, dans `.data/d1-migration/backup.key` avec accès local restreint.

Le propriétaire a explicitement autorisé l'export et l'import, ainsi que les
sauvegardes chiffrées du workflow de publication. Le workflow
[42225399950](https://github.com/dasbap/jeux_RPG/actions/runs/42225399950) a réussi.
L'artefact téléchargé contient uniquement la sauvegarde chiffrée, son checksum
et un rapport sans données personnelles. Le checksum a été vérifié.

## Import réel et restauration vérifiés

La vacuité de `jeux-rpg-import-preview` a été contrôlée, puis le schéma et le
fichier privé produit par `prepare_d1_import.py` ont été importés. Le contrôle
`verify_d1_import.py` confirme les tables durables et leurs séquences identiques
à la sauvegarde source : **707 lignes**, dont 23 comptes, 24 personnages,
27 sessions de compte, 16 parties/membres/tutoriels et 544 événements.

La comparaison inclut les mots de passe hachés, les sessions et les états JSON,
sans publier leurs valeurs. Elle normalise les REAL SQLite intégraux que le JSON
D1 représente comme des entiers (`0.0` devient `0`), sans arrondir les fractions.
Les relations et la réouverture du moteur importé sont valides.

Un export privé depuis ce vrai D1 a ensuite été restauré localement par
`export_database_backup.py` : intégrité, relations, tables et réouverture du moteur
réussies. Les preuves et copies privées restent dans `.data/d1-migration/`, hors Git.

L'import est une photographie ponctuelle, sans synchronisation continue. La
production actuelle reste sur Turso. Une recette complète du déploiement Vercel
D1 avec Redis reste à réaliser avant la bascule publique. Celle-ci exige un gel
des écritures, un nouvel export final et une comparaison, en conservant Turso
pour le retour arrière. Toute progression écrite ensuite sur D1 doit être
conservée avant un éventuel retour vers Turso.
