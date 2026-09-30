# Audit du moteur RPG — 30 septembre 2026

Révision de départ : `21e8d2be74b1fc3d5490a946878ce7d2ded57378`.

## Résultats locaux

- Python 3.12.14 sur Linux : 608 tests réussis, 6 ignorés, aucune erreur ni avertissement.
- Couverture des lignes : 83,77 %. Branches : 66,24 %. Score combiné : 79,60 %.
- Ruff : contrôles de syntaxe, variables indéfinies et comparaisons incorrectes réussis. Cette configuration cible les erreurs ; elle n'impose pas encore toutes les règles stylistiques de Ruff.
- Compilation Python réussie ; wheel construit, installé et lancé hors du dossier source.
- Benchmark indépendant : médiane de 0,085 s pour 100 créations de personnages, pic mémoire de 658 069 octets ; 100 duels en 0,036 s. Mesures indicatives sur cet environnement, avec seed fixe et maximum de 100 rounds par duel.

Les six exclusions comprennent quatre tests de l'application externe `bot.game.storage` absente et deux modules historiques de carte/POI déjà désactivés. Ces exclusions ne constituent pas une validation de ces fonctionnalités.

## Corrections

- Regroupement dans un paquet installable `jeuxRPG` : les imports restent identiques, les chemins physiques racine changent.
- Lancement réel via `python -m jeuxRPG`, `jeux-rpg` et `python main.py` ; commande et installation documentées.
- Préservation des fichiers JSON dans la distribution ; correction du chemin de configuration.
- Correction d'une f-string incompatible avec Python 3.10/3.11.
- Refus de consommation d'énergie négative.
- Suppression des récompenses répétées lorsque des dégâts sont appliqués à un personnage déjà mort.
- Transfert des membres lors d'une fusion d'équipes et nettoyage du chef lors de la destruction.
- Refus d'ajout d'un combattant adverse avant mutation du combat.
- Réservation atomique des participants dans le moteur concurrent.
- Suppression des effets expirés sans sauter les effets adjacents ; classification correcte des dégâts périodiques.
- Correction de la création des quartiers de la ville de base.
- Suppression du faux message de mort d'invocation provoqué par une comparaison d'identité avec une liste vide.
- Remplacement des scénarios HTTP Locust sans serveur correspondant par un benchmark du moteur.

## Automatisation

Quatre workflows : lint/syntaxe, tests/couverture sur Linux et Windows avec Python 3.10/3.12/3.13, packaging/lancement hors dépôt, performance. Les résultats locaux ne prouvent pas que les six environnements CI ont réussi ; seuls leurs runs GitHub Actions peuvent le confirmer.

## Limites et suites

L'inventaire reproductible `scripts/function_audit.py` recense 537 fonctions et 83 sans ligne de corps exécutée. Il associe le rôle documenté et les lignes manquantes ; il ne prouve pas la qualité des assertions. Le rapport JSON est publié comme artefact CI. La couverture doit encore progresser, notamment pour les actions de soin/résurrection, certains wrappers de navigation et de sauvegarde, et les erreurs des modes avancés.

L'équilibrage conserve ses tests historiques ; aucun ajustement arbitraire des statistiques métier n'a été effectué. Les benchmarks vérifient un budget large ; ils ne constituent pas une étude comparative avant/après ni une mesure de charge réseau.

Le moteur exécute les rounds en threads : un timeout ne peut pas interrompre instantanément un round Python déjà démarré. Les simulations d'équilibrage modifient certaines méthodes globales pendant leur collecte ; elles ne doivent pas être lancées en concurrence dans le même processus. Ces limites nécessitent une évolution dédiée avant un usage serveur concurrent.

## Extension : aventure persistante, équipements et craft

Le lancement par défaut enchaîne désormais des combats réels avec sauvegarde atomique et reprise. Le nouveau module `adventure` génère matériaux et recettes pour six familles de créatures, gère les pièces d'armure, le craft et les bonus de panoplie. Le mode interactif permet la gestion manuelle ; le mode automatique fabrique et équipe les améliorations. Voir `ADVENTURE.md`.

Régressions métier supplémentaires corrigées : l'XP des invocations revient au maître ; les invocations supprimées quittent le registre global ; les petits dégâts répartis sur les invocations ne déclenchent plus de perte de HP nulle invalide ; la sérialisation existante des statistiques ne tente plus une conversion `int` inutile. Dans l'arène, le prêtre dispose d'une attaque de base. Les ennemis sont générés directement à leur niveau sans progression récursive, avec équivalence vérifiée aux statistiques historiques.

Validation locale après extension : **677 tests réussis, 6 ignorés ; couverture combinée 82,28 %**. Ruff, compilation, création du wheel, installation hors dépôt, trois combats suivis de deux combats repris réussis. Le benchmark de 100 combats persistants dure environ 0,167 s pour une sauvegarde de 23 172 octets. Une série manuelle de 1 000 combats s'est achevée sans blocage en environ 20,5 s, avec une sauvegarde de 127 218 octets. Ces mesures dépendent de cet environnement et ne constituent pas un test de charge multijoueur.

Inventaire actualisé : 568 fonctions, dont 78 sans ligne de corps exécutée. Les six exclusions historiques restent inchangées. Les métriques et limites présentées au début de ce rapport décrivent l'audit initial ; cette section décrit l'état actuel.
