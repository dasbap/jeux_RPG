# Configuration restante pour la publication

État confirmé le 9 octobre 2026 après connexion au navigateur Vercel :

- Équipe `dasbaps-projects`, plan Hobby, projet `jeux-rpg`, ID `prj_fVH6vG7RCXf5OP3MIfTngxeCN8U2`.
- Production publique : `d85cbd9`, branche `alpha-vercel-turso`, déploiement `EFEv91d6NwdxGMeMybtxQkxgzNFr`.
- Version préparée : `9a5f1ea`, branche `prod`, déploiement `7SLGgBmQddDcSy5a7aC6G5sLmQ1B`, Ready / Production / Staged. Les domaines de production n'ont pas été attribués à cette version.
- Vercel Authentication activée, Legacy Standard Protection ; aucun secret Protection Bypass for Automation.
- GitHub possède déjà `VERCEL_TOKEN`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` au niveau dépôt. Aucun secret `VERCEL_AUTOMATION_BYPASS_SECRET`.
- L'environnement GitHub `production` ne contient ni secret ni reviewer obligatoire et n'a pas de restriction de branches.
- Redis/Upstash et Turso sont configurés dans Vercel ; seules les existences et les noms ont été consultés, jamais les valeurs.

## Action à effectuer par le propriétaire

1. Dans [Vercel / Deployment Protection](https://vercel.com/dasbaps-projects/jeux-rpg/settings/deployment-protection), section **Protection Bypass for Automation**, utiliser **Add Secret**. Créer un secret dédié aux vérifications GitHub Actions de ce projet. Garder l'authentification Vercel active.
2. Copier la valeur directement dans [GitHub / environnement production](https://github.com/dasbap/jeux_RPG/settings/environments/23864924947/edit), **Add environment secret**, nom exact **`VERCEL_AUTOMATION_BYPASS_SECRET`**. Ne pas la mettre dans une variable publique, le chat, un fichier ou les logs. Aucun nouveau `VERCEL_TOKEN` n'est demandé.
3. Dans ce même environnement, activer **Required reviewers** avec une personne capable de revoir et d'approuver le commit exact ; restreindre les branches autorisées à **`prod`**. La compétence [Vercel deployments-cicd](skill://plugin_connector_690a90ec05c881918afb6a55dc9bbaa1/deployments-cicd/SKILL.md) prescrit : « Run secret-bearing workflows only for reviewed code on a protected branch, or after a required environment reviewer approves the exact PR commit. »
4. Revoir et intégrer la PR #28 dans `master`, puis préparer une PR `master` → `prod`. Cette procédure met le dernier code vérifié à disposition du workflow existant, sans push direct sur production. Ne pas relancer aveuglément l'ancien déploiement `9a5f1ea`, qui ne contient pas les optimisations.
5. Vérifier les sauvegardes de données et les protections, puis exécuter le workflow **Publication Vercel jeux-rpg** sur le commit exact revu de `prod`. Il contrôle désormais la présence du secret avant build ou écriture Turso. Le healthcheck exige toujours le SHA attendu ; une réponse HTML ou HTTP 401/403 produit un diagnostic clair et bloque la promotion.
6. Conserver le déploiement public précédent. Promouvoir uniquement le build qui a réussi les vérifications, puis contrôler connexion, reprise et ressources.

Le secret de bypass autorise son détenteur à accéder aux versions protégées de ce projet. La saisie et la création de ce nouveau secret doivent être effectuées directement par le propriétaire ; l'assistant ne lit pas sa valeur.

## Validation déjà acquise

Commit `10678839b3c63efc77db0b94f39f11d06cbe198a`, PR #28 : tous les workflows terminés avec succès. Matrice Python 3.11/3.12/3.13, Redis réel en CI, tests Windows de l'éditeur, lint, installation, performance, UI et Playwright/HUD. Python 3.12 : **1 563 tests réussis, 7 ignorés**, 86,97 s. La dernière correction du vérificateur ajoute huit cas ciblés ; les nouveaux résultats CI doivent être vérifiés sur son commit avant publication.

Aucune nouvelle publication, création de secret, modification de protection, fusion ou écriture sur les données de production n'a été effectuée pendant ces contrôles.
