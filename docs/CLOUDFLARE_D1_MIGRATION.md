# Migration de Turso vers Cloudflare D1 — conception et prérequis

## État

Migration **non activée**. La production Vercel continue d'utiliser Turso. Ce document prépare une migration sans mettre en danger les sauvegardes des joueurs.

## Architecture vérifiée

- Application FastAPI Python déployée sur Vercel (`app:app`).
- Coordination temps réel par Redis et moteur SQLite en mémoire (`jeuxRPG/multiplayer/realtime.py` et `realtime_store.py`).
- Persistance vers Turso via le protocole HTTP libSQL (`jeuxRPG/multiplayer/turso.py`).
- Initialisation versionnée du schéma via `schema.initialize` et trois scripts SQL.
- Sauvegardes multi-tables avec `BEGIN IMMEDIATE`, contrôle `runtime_fence` puis `COMMIT` dans `RuntimeStore.persist`.
- Chargement cohérent avec acquisition de génération de moteur dans `RuntimeStore.load`.

## Contrainte bloquante

D1 ne fournit pas le protocole HTTP libSQL de Turso, ni une connexion SQLite à transactions interactives utilisable depuis le processus Python de Vercel. Un simple remplacement d'URL/jeton ou un proxy de requêtes SQL indépendantes casserait l'atomicité et le mécanisme `runtime_fence`.

**Ne pas** déplacer le contrôle de fence et les écritures dans des appels HTTP indépendants. **Ne pas** exécuter `BEGIN IMMEDIATE` et `COMMIT` comme si D1 maintenait une transaction entre deux requêtes.

## Adaptation retenue à implémenter

1. Provisionner une base D1 avec juridiction UE, en environnement de test distinct, et un Worker privé avec binding D1.
2. Fournir des opérations RPC explicites (pas de SQL arbitraire exposé) : `health`, `load_snapshot`, `persist_checkpoint`, `migrate`.
3. Dans le Worker, garantir l'atomicité de chaque checkpoint et le rejet d'un `fence` périmé avant tout changement d'état; concevoir et tester précisément la primitive de transaction D1. En l'absence de preuve de cette propriété, bloquer la bascule.
4. Ajouter un adaptateur Python appelé uniquement par `RuntimeStore.load/persist`; garder SQLite en mémoire et Redis inchangés.
5. Reprendre `0001_initial.sql`, `0002_receipt_expiry.sql`, `0003_guilds.sql` en testant la compatibilité D1 et la version de schéma.
6. Exporter Turso, importer dans la base D1 de test, contrôler les décomptes de lignes, les clés étrangères, la présence des comptes, les parties, l'inventaire et les journaux.
7. Tester concurrence entre deux propriétaires, perte du réseau, reprise Redis, non-régression des mots de passe/sessions et absence de double écriture.
8. Faire une sauvegarde finale; suspendre temporairement les écritures; synchroniser les dernières modifications; basculer les secrets de l'environnement Vercel puis exécuter les tests de validation. Conserver Turso pour retour arrière.

## Variables futures, non actives

- `RPG_DATABASE_BACKEND=d1`
- `RPG_D1_WORKER_URL`
- `RPG_D1_SERVICE_TOKEN`

Ne pas mettre de secrets dans Git ou exposer l'API SQL au navigateur. Le Worker doit authentifier les requêtes serveur et imposer des bornes de taille et de durée.

## RGPD

Archiver le DPA Cloudflare, vérifier sa portée contractuelle pour l'offre Free et documenter sous-traitants, transferts, rétention, effacement, sauvegardes et journalisation. La juridiction UE doit être paramétrée avant de créer la base.

## Critères de validation avant déploiement

- Tests automatisés du fence et de l'atomicité réussis sous accès concurrents.
- Migration de toutes les données testée avec comparaison avant/après.
- Aucun secret Turso supprimé avant recette et plan de retour arrière.
- Aucune activation en production depuis cette branche sans vérification spécifique.
