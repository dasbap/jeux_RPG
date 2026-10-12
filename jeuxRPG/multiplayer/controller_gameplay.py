from copy import deepcopy

from .gameplay_catalog import STATS, identifier


SECTIONS = [
    ("recipes", "Forge / recettes"),
    ("materials", "Matériaux"),
    ("slots", "Équipement"),
    ("rules", "Règles du jeu"),
    ("rare_costs", "Améliorations rares"),
    ("encounter_chain", "Groupes de rencontres"),
    ("summon_control", "Contrôle des invocations"),
    ("xp_classes", "Récompenses XP"),
    ("story", "Textes du tutoriel"),
]
FIXED = {"rules", "story"}
LABELS = {
    "time": "Temps et régénération",
    "movement": "Déplacements",
    "combat": "Combat et vision",
    "forge": "Forge et améliorations",
    "social": "Équipes et serveurs",
    "encounters": "Rencontres",
    "tutorial": "Premier combat et chasse",
    "travel": "Trajets et interruptions",
    "ai": "IA, furtivité et distances",
    "bleeding": "Saignement",
    "start": "Apparition initiale du personnage",
}
FIELD_LABELS = {
    "slot": "Emplacement d’équipement",
    "adjective": "Adjectif au niveau maximum",
    "quantity": "Quantité de matériau",
    "rare_chance": "Probabilité de drop rare par défaut",
    "game_ratio": "Secondes en jeu pour une seconde réelle",
    "action_seconds": "Intervalle des actions (secondes réelles)",
    "hp_regen_fraction": "Fraction des PV régénérée par intervalle",
    "hp_regen_interval": "Intervalle de régénération (secondes en jeu)",
    "resource_interval_real": "Intervalle des énergies (secondes réelles)",
    "walking_kmh": "Vitesse de marche (km/h)",
    "move_seconds": "Durée d’un pas",
    "stealth_move_seconds": "Durée d’un pas furtif",
    "mob_move_seconds": "Durée d’un pas de créature",
    "call_seconds": "Durée d’appel des renforts",
    "search_real_seconds": "Recherche de cible (secondes réelles)",
    "summon_vision": "Vision des invocations (cases)",
    "support_range": "Portée de soutien par défaut",
    "effect_factor": "Multiplicateur de puissance par défaut",
    "stat_factor": "Part de la statistique dans la puissance",
    "level_xp_base": "Base du facteur XP de niveau",
    "level_xp_limit": "Écart de niveau pris en compte",
    "level_xp_divisor": "Diviseur de l’écart de niveau",
    "max_level": "Niveau maximum d’amélioration",
    "hp_per_level": "PV supplémentaires par amélioration",
    "stat_every_levels": "Niveaux par bonus de statistique",
    "cost_linear": "Croissance linéaire du coût",
    "cost_quadratic": "Croissance quadratique du coût",
    "team_capacity": "Joueurs maximum par équipe",
    "realm_capacity": "Joueurs maximum par serveur",
    "friend_capacity": "Taille maximale de la liste d’amis",
    "factor_min": "Facteur minimum",
    "factor_max": "Facteur maximum",
    "difficulty_base": "Base du facteur de difficulté",
    "level_divisor": "Niveaux par palier de difficulté",
    "delta_limit": "Écart de difficulté pris en compte",
    "hp_first": "PV du gobelin au premier combat",
    "hp_hunt": "PV du gobelin pendant la chasse",
    "xp_first": "XP du premier combat",
    "xp_hunt": "XP du combat de chasse",
    "encounter_chance": "Probabilité de rencontre pendant le trajet",
    "segment_max_seconds": "Durée maximale d’un segment",
    "segment_min_fraction": "Fraction minimale du trajet",
    "segment_random_fraction": "Fraction aléatoire du trajet",
    "energy_regen_min": "Régénération d’énergie minimale",
    "energy_regen_max": "Régénération d’énergie maximale",
    "energy_regen_fraction": "Taux de régénération maximum",
    "energy_regen_divisor": "Diviseur du taux de régénération",
    "cost_min": "Coût minimum des compétences",
    "cost_factor": "Facteur de coût par défaut",
    "physical_cast": "Incantation physique par défaut",
    "summon_cast": "Incantation d’invocation par défaut",
    "magic_cast": "Incantation magique par défaut",
    "melee_range": "Portée des attaques au corps à corps",
    "detection_range": "Distance de détection",
    "hidden_detection_range": "Détection des unités cachées",
    "cover_range": "Distance pour utiliser une couverture",
    "corpse_interact_range": "Distance de dépeçage",
    "corpse_detection_range": "Distance de détection des corps",
    "ally_call_range": "Distance d’appel des alliés",
    "summon_follow_range": "Distance de suivi d’invocation",
    "summon_attack_seconds": "Attaque d’invocation (secondes réelles)",
    "mob_windup_seconds": "Préparation d’attaque (secondes en jeu)",
    "mob_attack_min_seconds": "Attaque de mob : délai minimum",
    "mob_attack_random_seconds": "Attaque de mob : délai aléatoire",
    "damage_min": "Dégâts minimaux de saignement",
    "force_factor": "Part de la force dans le saignement",
    "tick_real_seconds": "Intervalle de saignement (secondes réelles)",
    "ticks": "Nombre de dégâts successifs",
    "start_level": "Première amélioration utilisant ce matériau",
    "offset": "Niveau soustrait pour le coût rare",
    "divisor": "Niveaux par matériau rare",
    "energy": "Énergie consommée",
    "per_second": "Coût de contrôle par seconde",
    "factor": "Multiplicateur XP",
}


def catalog(project, section):
    return project.content["gameplay"][section]


def rows(project, section):
    values = catalog(project, section)
    if section == "rules":
        return [
            (
                key,
                LABELS[key],
                " · ".join(f"{name} : {value}" for name, value in item.items()),
            )
            for key, item in values.items()
        ]
    if section == "slots":
        return [
            (key, value, "Emplacement d’équipement") for key, value in values.items()
        ]
    if section == "recipes":
        return [
            (
                key,
                value["name"],
                f"{value['slot']} · "
                + ", ".join(
                    f"{quantity} {item}" for item, quantity in value["cost"].items()
                ),
            )
            for key, value in values.items()
        ]
    if section == "materials":
        return [
            (key, value["name"], f"Drop rare : {value['rare_chance']:.1%}")
            for key, value in values.items()
        ]
    if section == "story":
        return [
            (key, value["name"], value["description"]) for key, value in values.items()
        ]
    if section == "summon_control":
        return [
            (key, key, f"{value['per_second']} {value['energy']} / seconde")
            for key, value in values.items()
        ]
    if section == "xp_classes":
        return [(key, key, f"XP × {value}") for key, value in values.items()]
    if section == "encounter_chain":
        return [
            (
                str(index),
                f"Créature {index + 1}",
                f"Probabilité successive : {value:.1%}",
            )
            for index, value in enumerate(values)
        ]
    return [
        (
            str(index),
            value["item"],
            f"À partir de +{value['start_level']} : (niveau − {value['offset']}) / {value['divisor']}",
        )
        for index, value in enumerate(values)
    ]


def references(project, section, key):
    gameplay = project.content["gameplay"]
    result = []
    if section in ("materials", "slots"):
        result.extend(
            "recettes/" + name
            for name, value in gameplay["recipes"].items()
            if key in value["cost"]
            if section == "materials"
        )
        if section == "slots":
            result.extend(
                "recettes/" + name
                for name, value in gameplay["recipes"].items()
                if value["slot"] == key
            )
    if section == "materials":
        result.extend(
            "améliorations/" + str(index)
            for index, value in enumerate(gameplay["rare_costs"])
            if value["item"] == key
        )
        result.extend(
            "mobs/" + name
            for name, value in project.mobs.items()
            if key in value.get("loot", {})
            or any(drop["item"] == key for drop in value.get("drops", []))
        )
    if section == "recipes":
        result.extend(
            "quêtes/" + value["id"]
            for value in project.content["quests"]
            if value["kind"] == "craft" and value["target"] == key
        )
        result.extend(
            "succès/" + value["id"]
            for value in project.content["achievements"]
            if value["condition"] == "craft" and value.get("target") == key
        )
    if section == "xp_classes":
        result.extend(
            "mobs/" + name
            for name, value in project.mobs.items()
            if value.get("xp_class", "normal") == key
        )
    return sorted(set(result))


def change(project, section, key, value=None, new=False, delete=False):
    before = project.state()
    try:
        values = catalog(project, section)
        if delete:
            if section in FIXED or references(project, section, key):
                raise ValueError(
                    "Définition encore utilisée : réaffectez ses références avant de la supprimer."
                )
            values.pop(int(key)) if isinstance(values, list) else values.pop(key)
        elif isinstance(values, list):
            values.append(deepcopy(value)) if new else values.__setitem__(
                int(key), deepcopy(value)
            )
        else:
            if (
                section not in FIXED
                and section != "summon_control"
                and not identifier(key)
            ):
                raise ValueError(
                    "Identifiant : lettres minuscules, chiffres et underscores."
                )
            if new and key in values:
                raise ValueError("Identifiant déjà utilisé.")
            values[key] = deepcopy(value)
        project.validate()
    except Exception:
        project.restore(before)
        raise
    return before


class ControllerGameplayMixin:
    def gameplay_selection(self, section):
        chosen = self.tables[section].selection()
        return chosen[0] if chosen else None

    def inspect_gameplay(self, section):
        key = self.gameplay_selection(section)
        if key is None:
            return
        values = catalog(self.project, section)
        result = {
            "définition": deepcopy(
                values[int(key)] if isinstance(values, list) else values[key]
            ),
            "utilisé_par": references(self.project, section, key),
        }
        if section == "recipes":
            from .forge import piece, upgrade_cost

            maximum = self.project.content["gameplay"]["rules"]["forge"]["max_level"]
            level = self.simpledialog.askinteger(
                "Aperçu de l’équipement",
                "Niveau d’amélioration",
                initialvalue=0,
                minvalue=0,
                maxvalue=maximum,
                parent=self.root,
            )
            if level is None:
                return
            result["équipement"] = piece(key, level, self.project.content["gameplay"])
            result["coût"] = (
                upgrade_cost(key, level, self.project.content["gameplay"])
                if level
                else values[key]["cost"]
            )
        self.show_report("Aperçu et références", result)

    def edit_gameplay(self, section, new=False):
        key = self.gameplay_selection(section)
        if not new and key is None:
            return
        try:
            result = self.gameplay_form(section, key, new)
            if result is None:
                return
            identifier, value = result
            if not new and identifier != key:
                raise ValueError(
                    "L’identifiant existant doit être conservé ; dupliquez la définition pour en créer une autre."
                )
            before = change(self.project, section, identifier, value, new)
            if self.project.state() != before:
                self.remember(before)
            self.refresh()
            self.status.set(
                "Modification appliquée. Enregistrez puis redémarrez le serveur pour appliquer les règles."
            )
        except (ValueError, KeyError, TypeError) as error:
            self.messagebox.showerror("Gameplay", str(error), parent=self.root)

    def gameplay_form(self, section, key, new):
        values = catalog(self.project, section)
        old = (
            None
            if new
            else deepcopy(values[int(key)] if isinstance(values, list) else values[key])
        )
        if section == "recipes":
            initial = old or {
                "name": "Nouvel équipement",
                "slot": next(iter(catalog(self.project, "slots"))),
                "adjective": "",
                "cost": {next(iter(catalog(self.project, "materials"))): 1},
            }
            result = self.form(
                "Recette et bonus",
                {
                    "id": key or "",
                    **{name: initial[name] for name in ("name", "slot", "adjective")},
                    **{stat: initial.get(stat, 0) for stat in STATS},
                },
                {"slot": list(catalog(self.project, "slots"))},
            )
            if result is None:
                return None
            costs = self.edit_records(
                "Matériaux de fabrication",
                [
                    {"item": item, "quantity": count}
                    for item, count in initial["cost"].items()
                ],
                {"item": next(iter(catalog(self.project, "materials"))), "quantity": 1},
                {"item": list(catalog(self.project, "materials"))},
            )
            if costs is None:
                return None
            if len({item["item"] for item in costs}) != len(costs):
                raise ValueError(
                    "Un matériau ne doit apparaître qu’une fois dans les coûts."
                )
            result["cost"] = {item["item"]: item["quantity"] for item in costs}
        elif section == "materials":
            result = self.form(
                "Matériau",
                {
                    "id": key or "",
                    **(old or {"name": "Nouveau matériau", "rare_chance": 0.0}),
                },
            )
        elif section == "slots":
            result = self.form(
                "Emplacement d’équipement",
                {"id": key or "", "name": old or "Nouvel emplacement"},
            )
        elif section == "rules":
            choices = {"map": list(self.project.maps)} if key == "start" else None
            result = self.form(LABELS[key], old, choices)
            return (key, result) if result is not None else None
        elif section == "story":
            result = self.form("Étape du tutoriel", old)
            return (key, result) if result is not None else None
        elif section == "xp_classes":
            result = self.form(
                "Récompense XP",
                {"id": key or "", "factor": float(old if old is not None else 1.0)},
            )
        elif section == "summon_control":
            from jeuxRPG._class.res.character.class_models import ENERGY_NAMES

            choices = [
                item["id"]
                for item in self.project.content["templates"]["classes"]
                if item["class_type"] == "INVOCATION"
            ]
            result = self.form(
                "Coût du contrôle",
                {
                    "id": key or (choices[0] if choices else ""),
                    **(old or {"energy": "Mana", "per_second": 0.4}),
                },
                {"id": choices, "energy": ENERGY_NAMES},
            )
        elif section == "encounter_chain":
            result = self.form(
                "Probabilité successive",
                {"chance": float(old if old is not None else 0.1)},
            )
            return (key, result["chance"]) if result is not None else None
        else:
            result = self.form(
                "Matériau d’amélioration",
                old
                or {
                    "item": next(iter(catalog(self.project, "materials"))),
                    "start_level": 1,
                    "offset": 0,
                    "divisor": 1,
                },
                {"item": list(catalog(self.project, "materials"))},
            )
            return (key, result) if result is not None else None
        if result is None:
            return None
        identifier = result.pop("id")
        value = (
            result["name"]
            if section == "slots"
            else result["factor"]
            if section == "xp_classes"
            else result
        )
        return identifier, value

    def delete_gameplay(self, section):
        selected = self.tables[section].selection()
        if not selected or not self.messagebox.askyesno(
            "Supprimer", "Supprimer cette définition ?", parent=self.root
        ):
            return
        try:
            before = change(self.project, section, selected[0], delete=True)
            self.remember(before)
            self.refresh()
        except (ValueError, KeyError, TypeError) as error:
            self.messagebox.showerror(
                "Suppression refusée", str(error), parent=self.root
            )

    def duplicate_gameplay(self, section):
        key = self.gameplay_selection(section)
        if key is None or section in FIXED:
            return
        values = catalog(self.project, section)
        copied = deepcopy(values[int(key)] if isinstance(values, list) else values[key])
        replacement = (
            None
            if isinstance(values, list)
            else self.simpledialog.askstring(
                "Dupliquer", "Identifiant de la copie", parent=self.root
            )
        )
        if not isinstance(values, list) and not replacement:
            return
        if isinstance(copied, dict) and "name" in copied:
            copied["name"] += " · copie"
        try:
            self.remember(change(self.project, section, replacement, copied, new=True))
            self.refresh()
        except (ValueError, KeyError, TypeError) as error:
            self.messagebox.showerror(
                "Duplication refusée", str(error), parent=self.root
            )
