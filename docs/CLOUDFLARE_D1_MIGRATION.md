# Migration de Turso vers Cloudflare D1 — réalisée

La bascule est terminée depuis le **6 novembre 2026**. La production publique
utilise D1, avec une base en juridiction UE et un Worker privé. Les données
réelles ont été transférées puis comparées, et une sauvegarde D1 a été restaurée.
Voir [les preuves de production](D1_PRODUCTION.md), [la préproduction datée](D1_PREPRODUCTION.md)
et [l’architecture actuelle](ARCHITECTURE.md).

## Architecture retenue et implémentée

- FastAPI/ASGI Python sur Vercel, interface JavaScript et WebSocket existants.
- Simulation SQLite en mémoire et coordination par Redis.
- `RuntimeStore.load/persist` choisit D1 avec `RPG_DATABASE_BACKEND=d1` et appelle
  `jeuxRPG/multiplayer/d1_client.py`.
- `cloudflare/d1-worker.mjs` authentifie les appels et expose les opérations
  `health`, `read_snapshot`, `load_snapshot` et `persist_checkpoint`.
- Les checkpoints multi-tables utilisent un lot D1 atomique avec contrôle de
  génération ; `cloudflare/0004_fence_guard.sql` fournit les triggers requis.
- Le schéma versionné est installé sur D1 avant publication. Le Worker ne
  fournit ni endpoint `migrate` ni exécution SQL arbitraire.

La migration a conservé le moteur Python et le client existants. D1 ne remplace
ni la simulation en RAM ni Redis.

## Contrainte traitée

D1 n’utilise pas le protocole libSQL de Turso. Les transactions interactives
`BEGIN IMMEDIATE` / `COMMIT` de l’ancien adaptateur ne sont pas découpées en
appels D1 indépendants. Le contrôle de génération et les écritures sont réunis
dans un lot atomique du Worker ; un ancien moteur ne doit pas pouvoir écraser
les changements d’un propriétaire plus récent.

## Configuration active

```text
RPG_DATABASE_BACKEND=d1
RPG_D1_WORKER_URL=https://<worker-prive>.workers.dev
RPG_D1_SERVICE_TOKEN=<secret-serveur>
```

La variable `RPG_DATABASE_BACKEND` de l’environnement GitHub `production` vaut
`d1` ; le healthcheck public a été revérifié le 13 novembre 2026. Le secret de
service reste côté serveur. Aucun secret Cloudflare ne doit être embarqué dans
les clients web, Windows, Linux ou Android.

## Ancien backend et récupération

L’adaptateur Turso et les outils d’export sont conservés pour l’historique et
la récupération. Turso reste verrouillé ; ce n’est plus la base active.
Une panne D1 ne provoque aucune écriture de secours vers Turso.

Après des écritures D1, un retour vers une ancienne sauvegarde Turso ferait
perdre la progression récente. Toute récupération doit repartir des données
D1 actuelles et de sauvegardes vérifiées. Les anciennes branches de migration
ont été archivées ; les outils sont intégrés dans `master` et `prod`.

## Validation et limites restantes

Les rapports D1 décrivent les contrôles réels de transfert, de restauration,
de comptes, de sessions et de reprise. Les tests locaux du Worker vérifient
également le rejet des générations périmées et l’annulation des lots invalides.
Ils ne mesurent pas la capacité à 40 WebSockets sur l’infrastructure actuelle.
Voir [les mesures et leur portée](ARCHITECTURE.md#mesures-disponibles-et-limites).

Le [dossier fournisseur](CLOUDFLARE_DATA_PROCESSING.md) conserve les références
contractuelles consultées à la migration ; la preuve technique de la bascule
ne constitue pas une certification juridique.
