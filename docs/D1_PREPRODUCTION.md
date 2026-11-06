# Préproduction D1 — 6 novembre 2026

## Réalisé

La base `jeux-rpg-preview` a été créée avec `--jurisdiction eu` dans le compte
Cloudflare déjà connecté. Son identifiant et le binding `DB` sont dans
`cloudflare/wrangler.preview.json`. Le schéma du jeu (version 3) et les deux triggers
de protection de génération du moteur sont installés.

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

Les données fictives ont été retirées par le script. Il reste des métadonnées
techniques et une génération de moteur : cette base de recette n'est donc pas
une destination vide pour un import de production. Utiliser une **nouvelle base
D1 de recette vide** pour cet import, puis y appliquer le même schéma.

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
Le workflow de production n'a pas encore été modifié ni exécuté pour D1.

## Autorisations encore nécessaires

La PR [#90](https://github.com/dasbap/jeux_RPG/pull/90) prépare un export Turso
en lecture seule, chiffré avec age et conservé sept jours dans un artefact GitHub.
Tous ses contrôles GitHub sont verts. La clé privée est conservée uniquement sur
le poste, dans `.data/d1-migration/backup.key` avec accès local restreint.

La revue automatique a refusé le lancement de cet export tant que le propriétaire
n'a pas explicitement autorisé les données concernées et leur destination GitHub.
Elle a également refusé d'adapter les sauvegardes du workflow de production à D1
sans accord distinct sur ces futurs exports chiffrés. Aucun contournement n'est
prévu. Ces deux autorisations sont demandées dans la conversation.

## Après autorisation de l'export

Fusionner la PR #90 normalement, déclencher le workflow manuel depuis `master`,
télécharger et déchiffrer l'artefact dans le dossier privé local. Créer une base D1
de recette neuve, y appliquer le SQL produit par `scripts/prepare_d1_schema.py`,
puis importer le fichier produit par `scripts/prepare_d1_import.py`.

Comparer intégralement les tables durables et leurs séquences avec
`python -m scripts.verify_d1_import SOURCE --env-file ENV_D1`, sans modifier la
génération du moteur distant. Tester ensuite les parcours de préproduction.
Une bascule finale exige un gel des écritures et une nouvelle sauvegarde ;
la production actuelle reste sur Turso jusqu'à cette validation.
