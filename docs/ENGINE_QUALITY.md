# Qualité du moteur

Le moteur Python et ses stubs, dans `jeuxRPG`, suivent une configuration commune dans `pyproject.toml`. Les commandes locales et la CI utilisent Ruff 0.16.10, avec Python 3.11 comme version minimale.

## Règles contrôlées

- Formatage Ruff sur tout le moteur : indentation de quatre espaces, guillemets doubles et découpage uniforme des expressions.
- Imports triés, imports inutilisés supprimés, exports conservés explicitement lorsqu’ils font partie de l’API utilisée.
- Annotations modernes avec les collections natives et les unions `|` ; références anticipées conservées sous forme de chaînes lorsque nécessaire.
- Aucun diagnostic de lint accepté, aucune exception par fichier et aucun `noqa` dans le moteur.
- Complexité cyclomatique maximale de 20 pour chaque fonction, sans budget spécial pour les anciennes fonctions.
- Paramètres mutables interdits ; variables de boucle capturées explicitement et associations de collections vérifiées avec `zip(strict=True)` ou `pairwise` selon leur sens.
- Couverture minimale conservée : 77 % des lignes et 70 % des branches.
- Duplication AST plafonnée à 22 groupes et 24 occurrences supplémentaires, contre 43 et 48 auparavant.

## Réorganisation

Les validations de cartes, classes, objectifs et ressources ont des fonctions distinctes par responsabilité. Le contrôleur sépare les opérations d’édition et de renommage. Les commandes sociales et de session, les actions du combat et la CLI possèdent des traitements spécialisés. Le transport distingue l’origine, l’authentification, l’abonnement WebSocket, les réponses statiques et le traitement des commandes.

Le repos du personnage, le limiteur réseau local, les champs décimaux du contrôleur, les références des groupes de chat et le traitement des ennemis vaincus par les invocations partagent désormais leurs implémentations.

L’initialisation du personnage ne masque plus une erreur du sous-système de navigation. Les tests contrôlent cette propagation, les commandes interactives, les décimaux, les sauvegardes, les autorisations, les combats et les pannes de transport.

## Vérification

```bash
python -m ruff check jeuxRPG
python -m ruff format --check jeuxRPG
python -m compileall -q jeuxRPG main.py app.py scripts
python -m pytest -q --cov=jeuxRPG --cov-branch --cov-report=json:coverage.json
python scripts/quality_budget.py --coverage coverage.json
```

La CI complète ajoute trois versions de Python, Redis réel, les éditeurs graphiques sous Windows, les parcours web, l’installation du package et les mesures de performance.

## Interprétation des mesures

Le nettoyage supprime les 457 diagnostics historiques et les 152 anomalies de tri des imports mesurés au départ. Les 31 diagnostics de complexité supérieure à 20 disparaissent également.

Le détecteur de duplication compare des fenêtres de trois instructions identiques, d’au moins vingt nœuds AST. Les fenêtres peuvent se chevaucher et concerner des initialisations ou des structures de données similaires : il ne démontre pas que chaque ressemblance doit devenir une abstraction commune.

Ces contrôles rendent les exigences de qualité vérifiables et empêchent les régressions mesurées. Ils ne constituent pas une preuve d’absence universelle de bugs ou de dette technique. La couverture reste partielle ; les essais Windows et web sont automatisés, et une recette humaine peut toujours révéler un problème absent des scénarios actuels.
