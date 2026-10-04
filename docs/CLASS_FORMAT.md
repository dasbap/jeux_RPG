# Format universel des classes

Le catalogue `maps/classes.json` contient `version`, `kind: "classes"`, `maps: {}`, une liste `classes` et un dictionnaire `skills`. `maps` vide permet de partager le dossier avec les cartes. Le contrôleur sauvegarde ce catalogue avec les autres fichiers du projet. `RPG_CLASSES_FILE` permet de sélectionner un catalogue externe.

Chaque classe possède :

| Champ | Utilisation |
| --- | --- |
| `id`, `name`, `playable` | Identifiant unique, libellé, disponibilité à la création |
| `class_type` | Type du moteur, par exemple `DAMAGE`, `SHIELD`, `HEAL`, `SUMMONER` ou `INVOCATION` |
| `base_stats` | `hp`, `force`, `endurance`, `intelligence`, `sagesse` |
| `energies` | Liste `{type, value, regen_rate}`, types `Mana`, `Aura`, `Foie` |
| `growth` | Paliers `{level, stats, energies, unlock_energies}` |
| `skills` | Affectations `{level, skill_id, range?, cost?}` |
| `combat` | `attack_stat`, `attack_base`, `attack_factor`, `attack_min`, `attack_range`, `summoner`, `xp_factor` |
| `weaknesses`, `resistances` | Types de dégâts reconnus par le moteur |
| `previous_ids` | Identifiants anciens conservés lors d’un renommage |

Les gains d’un palier sont cumulatifs à chaque niveau où son seuil est atteint. Les clés de statistiques des paliers sont `HP`, `Force`, `Endurance`, `Intelligence`, `Sagesse`. `unlock_energies` crée une énergie une seule fois. Les niveaux des compétences humaines s’écrivent `level 1`, `level 5`, etc. Les invocations conservent leurs paliers tels que `BL`.

Une compétence réutilisable décrit son `type`, son `damage_type`, son énergie, son coût, son cooldown, ses conditions de ciblage et ses `effects`. Les effets décrivent valeur, durée, statistique visée, altération et éventuellement une invocation `{class, level}`. `balance` contient les paramètres de coût, de scaling et de saignement. `casting`, facultatif, définit le temps d’incantation et la concentration. Seuls les gestionnaires autorisés `default` et `damage_stun` sont acceptés ; le catalogue n’exécute aucun code fourni par l’utilisateur.

Les champs de compatibilité `table_id`, `advantage_format` et `formulas` préservent les imports et anciens personnages. Les nouvelles classes n’ont besoin d’aucune classe Python dédiée ni d’un `base_class`. Pour créer une variante, copiez une définition dans le contrôleur, choisissez un identifiant inédit puis ajustez ses données. Redémarrez le serveur après sauvegarde.
