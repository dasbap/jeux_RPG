# Bascule D1 de production — 6 novembre 2026

## État

**Bascule terminée et vérifiée.** Le site public
[jeux-rpg.vercel.app](https://jeux-rpg.vercel.app/) utilise D1. Lors de la bascule
du 6 novembre, son [healthcheck](https://jeux-rpg.vercel.app/health) annonçait
`database_backend=d1` et le SHA `86368f282af7fb0975bd21da5d79d6afa3adf021`.
Ce SHA désigne cette publication historique, pas chaque déploiement ultérieur.

Le 13 novembre 2026, le healthcheck public a été relu : `status=ok` et
`database_backend=d1`. L’environnement GitHub `production` sélectionne toujours
`RPG_DATABASE_BACKEND=d1`. L’[architecture actuelle](ARCHITECTURE.md) précise
les modes d’exécution, les fréquences de synchronisation et les limites des tests
à 40 joueurs ; ces vérifications de disponibilité ne sont pas un test de charge.

## Transfert final

Le propriétaire a explicitement autorisé le déchiffrement de la sauvegarde des
joueurs, son transfert dans la base européenne `jeux-rpg-production` via le
Worker `jeux-rpg-d1`, puis l'activation D1 et la publication Vercel.

Le trafic a été mis en pause et les anciennes connexions ont été drainées pendant
six minutes. Le workflow d'export final
[42237506730](https://github.com/dasbap/jeux_RPG/actions/runs/42237506730) a verrouillé
les anciens moteurs Turso avant la sauvegarde cohérente, sa restauration de
contrôle et son chiffrement age. L'archive chiffrée est conservée sept jours dans
GitHub. Sa clé privée reste dans le dossier local privé, hors Git.

La cible D1 a été créée avec `--jurisdiction eu`, puis initialisée au schéma 3 avec
ses deux protections contre les générations de moteur périmées. Son identifiant
et son binding sont dans `cloudflare/wrangler.production.json`.

La comparaison source/destination confirme :

| Données à la bascule | Nombre |
| --- | --- |
| Comptes | 23 |
| Personnages | 24 |
| Sessions de compte | 27 |
| Parties, membres et tutoriels | 16 de chaque |
| Événements | 544 |
| Ensemble des lignes durables | 707 |

Les tables et séquences sont identiques. Seul `meta.runtime_fence` est remis à
zéro dans le nouveau backend, explicitement, pour sa coordination indépendante ;
le verrou élevé est conservé dans Turso. Aucune progression n'est réinitialisée.
Les valeurs personnelles, mots de passe hachés et jetons ne sont pas publiés.

Le D1 importé a ensuite été exporté et restauré localement avec succès :
intégrité, relations et réouverture du moteur vérifiées. Les preuves détaillées
et les copies privées restent sous `.data/d1-migration/`, ignoré par Git.

## Publication

La PR [#92](https://github.com/dasbap/jeux_RPG/pull/92) sécurise le transfert et
le contrôle du backend. La PR [#93](https://github.com/dasbap/jeux_RPG/pull/93)
publie le SHA `86368f282af7fb0975bd21da5d79d6afa3adf021` sur `prod`.
Le workflow [42238015895](https://github.com/dasbap/jeux_RPG/actions/runs/42238015895)
teste le moteur et l'interface, restaure et chiffre une sauvegarde D1 conservée
trente jours, vérifie Redis/D1 et construit un artefact Vercel. La promotion
exige le bon SHA, `database_backend=d1`, les routes, les comptes, le tutoriel,
le WebSocket, les checkpoints et les lectures d'état en RAM sans appel distant.

Le workflow a réussi à sa deuxième tentative. Le déploiement actif Vercel est
`dpl_AT5PF7zBSEKFy3ewHCWzVdXojxRh`, état `READY`, cible `production`. Le projet
n'est plus en pause.

La première tentative Vercel a été annulée : un déploiement créé pendant la
pause du projet reste bloqué. La seconde est exécutée après levée de cette
pause ; Turso reste verrouillé pour empêcher les anciens moteurs d'enregistrer.

## Vérification du site public

Une recette Chromium sur le domaine public a validé l'affichage, l'inscription,
la création d'un personnage, le tutoriel, le checkpoint, puis la connexion par
mot de passe dans un contexte navigateur neuf et la reprise de la même partie.
Les lectures d'état sont servies en RAM avec zéro aller-retour distant ; aucune
erreur JavaScript de page n'est relevée.

Une lecture directe du D1 de production confirme la présence du compte de
contrôle et de sa partie, ainsi que de tous les identifiants des comptes et
personnages migrés. Les deux comptes de recette (publication et navigateur)
expliquent le passage de 23 à 25 comptes et de 24 à 26 personnages après les tests.
Les identifiants et secrets de recette ne sont pas publiés.

## Exploitation et récupération

Les déploiements D1 utilisent `RPG_DATABASE_BACKEND=d1`, `RPG_D1_WORKER_URL` et
`RPG_D1_SERVICE_TOKEN`. Ils n'ouvrent aucune connexion Turso et ne reviennent pas
silencieusement vers ce fournisseur en cas de panne. Redis utilise un espace
distinct dérivé de l'URL du Worker de production.

Turso est conservé comme source de récupération verrouillée. Après les premières
écritures de joueurs sur D1, ne pas simplement déverrouiller Turso ni promouvoir
un ancien déploiement : il faut préserver et reprendre la progression D1 actuelle
pour éviter un retour à des données périmées. Une récupération avant toute
écriture D1 peut utiliser la génération précédente du rapport de gel.
