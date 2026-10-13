import math
import re
from copy import deepcopy

STATS = ("hp", "endurance", "force", "intelligence", "sagesse")
DEFAULTS = {
    "materials": {
        key: {"name": name, "rare_chance": chance}
        for key, name, chance in [
            ("peau", "Peau", 0.0),
            ("croc", "Croc", 0.0),
            ("peau_gobelin", "Peau de gobelin", 0.0),
            ("croc_gobelin", "Croc de gobelin", 0.0),
            ("oreille_gobelin", "Oreille de gobelin", 0.0),
            ("cristal_gobelin", "Cristal de gobelin", 0.08),
            ("noyau_gobelin", "Noyau de gobelin", 0.02),
        ]
    },
    "slots": {
        "head": "Tête",
        "torso": "Torse",
        "hands": "Mains",
        "legs": "Jambes",
        "feet": "Pieds",
        "waist": "Taille",
    },
    "recipes": {
        "casque": {
            "slot": "head",
            "name": "Casque de la lisière",
            "adjective": "raffiné",
            "cost": {"peau": 2, "croc": 1},
            "hp": 3,
            "endurance": 1,
            "intelligence": 2,
            "sagesse": 1,
        },
        "veste": {
            "slot": "torso",
            "name": "Veste de la lisière",
            "adjective": "solide",
            "cost": {"peau": 2, "croc": 3},
            "hp": 10,
            "endurance": 3,
        },
        "gants": {
            "slot": "hands",
            "name": "Gants de la lisière",
            "adjective": "précis",
            "cost": {"peau": 2, "croc": 2},
            "hp": 2,
            "endurance": 1,
            "force": 2,
        },
        "jambieres": {
            "slot": "legs",
            "name": "Jambières de la lisière",
            "adjective": "robustes",
            "cost": {"peau": 3, "croc": 2},
            "hp": 5,
            "endurance": 2,
            "force": 1,
        },
        "bottes": {
            "slot": "feet",
            "name": "Bottes de la lisière",
            "adjective": "agiles",
            "cost": {"peau": 2, "croc": 1},
            "hp": 3,
            "endurance": 1,
            "sagesse": 1,
        },
        "ceinture": {
            "slot": "waist",
            "name": "Ceinture de la lisière",
            "adjective": "renforcée",
            "cost": {"peau": 1, "croc": 2},
            "hp": 2,
            "endurance": 1,
            "intelligence": 1,
            "sagesse": 2,
        },
    },
    "rules": {
        "time": {
            "game_ratio": 3.0,
            "action_seconds": 1.2,
            "hp_regen_fraction": 0.01,
            "hp_regen_interval": 60.0,
            "resource_interval_real": 1.0,
            "energy_regen_min": 0.2,
            "energy_regen_max": 1.5,
            "energy_regen_fraction": 0.1,
            "energy_regen_divisor": 10.0,
        },
        "movement": {
            "walking_kmh": 6.0,
            "move_seconds": 1.2,
            "stealth_move_seconds": 2.4,
            "mob_move_seconds": 2.4,
            "call_seconds": 6.0,
            "search_real_seconds": 10.0,
        },
        "combat": {
            "summon_vision": 6,
            "support_range": 6.0,
            "effect_factor": 0.55,
            "stat_factor": 0.25,
            "level_xp_base": 4.0,
            "level_xp_limit": 10.0,
            "level_xp_divisor": 10.0,
            "cost_min": 5,
            "cost_factor": 1.5,
            "physical_cast": 0.4,
            "summon_cast": 2.0,
            "magic_cast": 1.5,
        },
        "forge": {
            "max_level": 10,
            "hp_per_level": 2,
            "stat_every_levels": 2,
            "cost_linear": 1,
            "cost_quadratic": 1,
        },
        "social": {"team_capacity": 4, "realm_capacity": 40, "friend_capacity": 200},
        "encounters": {
            "factor_min": 0.25,
            "factor_max": 1.5,
            "difficulty_base": 2.0,
            "level_divisor": 5.0,
            "delta_limit": 10.0,
        },
        "tutorial": {"hp_first": 18, "hp_hunt": 24, "xp_first": 50, "xp_hunt": 50},
        "travel": {
            "encounter_chance": 0.25,
            "segment_max_seconds": 150.0,
            "segment_min_fraction": 0.15,
            "segment_random_fraction": 0.7,
        },
        "ai": {
            "melee_range": 1.5,
            "detection_range": 6.0,
            "hidden_detection_range": 1.5,
            "cover_range": 1.5,
            "corpse_interact_range": 1.5,
            "corpse_detection_range": 5.0,
            "ally_call_range": 10.0,
            "summon_follow_range": 2.0,
            "summon_attack_seconds": 3.0,
            "mob_windup_seconds": 1.8,
            "mob_attack_min_seconds": 9.0,
            "mob_attack_random_seconds": 6.0,
        },
        "bleeding": {
            "damage_min": 2,
            "force_factor": 0.05,
            "tick_real_seconds": 2.0,
            "ticks": 3,
        },
        "start": {"map": "clearing", "x": 1, "y": 10},
    },
    "rare_costs": [
        {"item": "cristal_gobelin", "start_level": 4, "offset": 2, "divisor": 2},
        {"item": "noyau_gobelin", "start_level": 8, "offset": 7, "divisor": 1},
    ],
    "encounter_chain": [0.9, 0.3, 0.1, 0.03, 0.001],
    "summon_control": {"Squelette": {"energy": "Mana", "per_second": 0.4}},
    "xp_classes": {
        "normal": 1.0,
        "warrior": 1.5,
        "caster": 1.8,
        "elite": 2.5,
        "boss": 4.0,
    },
    "story": {
        key: {"name": name, "description": description}
        for key, name, description in [
            (
                "clearing",
                "Clairière des Éveillés",
                "Explorez la clairière pour rencontrer votre premier gobelin.",
            ),
            (
                "first_fight",
                "Clairière des Éveillés",
                "Utilisez vos compétences ou votre attaque pour battre le gobelin.",
            ),
            (
                "road",
                "Sentier de Rosée",
                "Votre premier combat est gagné. Rejoignez le village de Rosée.",
            ),
            (
                "village",
                "Village de Rosée",
                "Parlez à Mira pour accepter sa quête de chasse.",
            ),
            (
                "hunt",
                "Lisière de Rosée",
                "Battez trois gobelins puis rapportez la nouvelle à Mira.",
            ),
            (
                "craft",
                "Forge de Rosée",
                "Fabriquez et équipez une veste avec les matériaux des gobelins.",
            ),
            (
                "travel",
                "Route des Deux Villages",
                "Votre équipement est prêt. Rejoignez le village de Brume.",
            ),
            (
                "complete",
                "Village de Brume",
                "Tutoriel terminé : combat, compétences, quête, butin et équipement maîtrisés.",
            ),
        ]
    },
}
LIMITS = {
    "game_ratio": (0.1, 100),
    "action_seconds": (0.05, 60),
    "hp_regen_fraction": (0, 1),
    "hp_regen_interval": (1, 86400),
    "resource_interval_real": (0.05, 60),
    "walking_kmh": (0.1, 1000),
    "move_seconds": (0.01, 60),
    "stealth_move_seconds": (0.01, 60),
    "mob_move_seconds": (0.01, 60),
    "call_seconds": (0, 300),
    "search_real_seconds": (0, 300),
    "summon_vision": (1, 64),
    "support_range": (0, 64),
    "effect_factor": (0, 100),
    "stat_factor": (0, 100),
    "level_xp_base": (1, 100),
    "level_xp_limit": (1, 100),
    "level_xp_divisor": (0.1, 100),
    "max_level": (0, 100),
    "hp_per_level": (0, 10000),
    "stat_every_levels": (1, 100),
    "cost_linear": (0, 10000),
    "cost_quadratic": (0, 10000),
    "team_capacity": (1, 40),
    "realm_capacity": (1, 200),
    "friend_capacity": (1, 2000),
    "factor_min": (0.01, 10),
    "factor_max": (0.01, 10),
    "difficulty_base": (1, 10),
    "level_divisor": (0.1, 100),
    "delta_limit": (1, 100),
    "hp_first": (1, 100000),
    "hp_hunt": (1, 100000),
    "xp_first": (0, 100000),
    "xp_hunt": (0, 100000),
    "encounter_chance": (0, 1),
    "segment_max_seconds": (1, 86400),
    "segment_min_fraction": (0, 1),
    "segment_random_fraction": (0, 1),
    "energy_regen_min": (0, 100),
    "energy_regen_max": (0, 100),
    "energy_regen_fraction": (0, 1),
    "energy_regen_divisor": (0.01, 10000),
    "cost_min": (0, 10000),
    "cost_factor": (0, 100),
    "physical_cast": (0, 300),
    "summon_cast": (0, 300),
    "magic_cast": (0, 300),
    "melee_range": (0.1, 64),
    "detection_range": (0.1, 64),
    "hidden_detection_range": (0, 64),
    "cover_range": (0, 64),
    "corpse_interact_range": (0.1, 64),
    "corpse_detection_range": (0, 64),
    "ally_call_range": (0, 64),
    "summon_follow_range": (0, 64),
    "summon_attack_seconds": (0.05, 300),
    "mob_windup_seconds": (0.05, 300),
    "mob_attack_min_seconds": (0.05, 300),
    "mob_attack_random_seconds": (0, 300),
    "damage_min": (0, 10000),
    "force_factor": (0, 100),
    "tick_real_seconds": (0.05, 300),
    "ticks": (1, 100),
    "x": (0, 127),
    "y": (0, 127),
}


def numeric(value, low, high, integer=False):
    return (
        type(value) in ((int,) if integer else (int, float))
        and math.isfinite(value)
        and low <= value <= high
    )


def identifier(value):
    return (
        isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,64}", value) is not None
    )


def named_catalog(values, title):
    if not isinstance(values, dict) or not 1 <= len(values) <= 200:
        raise ValueError(title + " : catalogue de 1 à 200 éléments requis.")
    for key, value in values.items():
        if (
            not identifier(key)
            or not isinstance(value, dict)
            or not isinstance(value.get("name"), str)
            or not 1 <= len(value["name"]) <= 100
        ):
            raise ValueError(title + " : identifiant ou nom invalide.")


def validate_rules(rules):
    if not isinstance(rules, dict) or set(rules) != set(DEFAULTS["rules"]):
        raise ValueError("Groupes de règles incomplets ou inconnus.")
    for group, defaults in DEFAULTS["rules"].items():
        values = rules[group]
        if not isinstance(values, dict) or set(values) != set(defaults):
            raise ValueError(group + " : paramètres incomplets ou inconnus.")
        for key, initial in defaults.items():
            if group == "start" and key == "map":
                if not identifier(values[key]):
                    raise ValueError("Carte de départ invalide.")
                continue
            if not numeric(values[key], *LIMITS[key], integer=type(initial) is int):
                raise ValueError(key + " : valeur hors limites ou type invalide.")
    if rules["encounters"]["factor_min"] > rules["encounters"]["factor_max"]:
        raise ValueError("Rencontres : facteur minimum supérieur au maximum.")
    if rules["social"]["team_capacity"] > rules["social"]["realm_capacity"]:
        raise ValueError("Une équipe ne peut pas dépasser la capacité du serveur.")
    if rules["time"]["energy_regen_min"] > rules["time"]["energy_regen_max"]:
        raise ValueError("Régénération : minimum supérieur au maximum.")
    if (
        rules["travel"]["segment_min_fraction"]
        + rules["travel"]["segment_random_fraction"]
        > 1
    ):
        raise ValueError("Trajet : somme des fractions supérieure à 1.")
    combat = rules["combat"]
    if (
        math.log10(combat["level_xp_base"])
        * combat["level_xp_limit"]
        / combat["level_xp_divisor"]
        > 6
    ):
        raise ValueError(
            "XP : multiplicateur de différence de niveau supérieur à un million."
        )


def validate_recipes(data):
    named_catalog(data["recipes"], "Recettes")
    slots = data["slots"]
    if (
        not isinstance(slots, dict)
        or not 1 <= len(slots) <= 32
        or any(
            not identifier(key)
            or not isinstance(value, str)
            or not 1 <= len(value) <= 100
            for key, value in slots.items()
        )
    ):
        raise ValueError("Emplacements d’équipement invalides.")
    for value in data["recipes"].values():
        if (
            set(value) - {"name", "slot", "adjective", "cost", *STATS}
            or value.get("slot") not in slots
            or not isinstance(value.get("adjective"), str)
            or len(value["adjective"]) > 100
        ):
            raise ValueError("Recette : emplacement, attribut ou adjectif invalide.")
        costs = value.get("cost")
        if (
            not isinstance(costs, dict)
            or not costs
            or any(
                key not in data["materials"] or not numeric(amount, 1, 1000000, True)
                for key, amount in costs.items()
            )
        ):
            raise ValueError("Recette : matériau inconnu ou quantité invalide.")
        if any(not numeric(value.get(stat, 0), 0, 100000, True) for stat in STATS):
            raise ValueError("Recette : bonus entier positif ou nul requis.")
    if "veste" not in data["recipes"] or data["recipes"]["veste"]["slot"] != "torso":
        raise ValueError(
            "La recette veste et son emplacement torso sont requis pour les anciennes sauvegardes et le tutoriel."
        )


def validate(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULTS):
        raise ValueError("Catalogues de gameplay incomplets ou inconnus.")
    named_catalog(data["materials"], "Matériaux")
    for value in data["materials"].values():
        if set(value) != {"name", "rare_chance"} or not numeric(
            value["rare_chance"], 0, 1
        ):
            raise ValueError("Matériau : probabilité de drop rare invalide.")
    validate_rules(data["rules"])
    validate_recipes(data)
    chain = data["encounter_chain"]
    if (
        not isinstance(chain, list)
        or not 1 <= len(chain) <= 40
        or any(not numeric(value, 0, 1) for value in chain)
    ):
        raise ValueError("Rencontres : probabilités successives invalides.")
    costs = data["rare_costs"]
    if not isinstance(costs, list) or len(costs) > 200:
        raise ValueError("Coûts rares invalides.")
    for item in costs:
        if (
            not isinstance(item, dict)
            or set(item) != {"item", "start_level", "offset", "divisor"}
            or item["item"] not in data["materials"]
            or not numeric(item["start_level"], 1, 100, True)
            or not numeric(item["offset"], 0, item["start_level"] - 1, True)
            or not numeric(
                item["divisor"], 1, item["start_level"] - item["offset"], True
            )
        ):
            raise ValueError("Coût rare : matériau, seuil ou formule invalide.")
    controls = data["summon_control"]
    if not isinstance(controls, dict) or len(controls) > 200:
        raise ValueError("Contrôles des invocations invalides.")
    for key, value in controls.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(value, dict)
            or set(value) != {"energy", "per_second"}
            or not isinstance(value["energy"], str)
            or not value["energy"]
            or not numeric(value["per_second"], 0, 10000)
        ):
            raise ValueError("Invocation : énergie ou coût de contrôle invalide.")
    xp_classes = data["xp_classes"]
    if (
        not isinstance(xp_classes, dict)
        or not xp_classes
        or len(xp_classes) > 100
        or any(
            not identifier(key) or not numeric(value, 0, 100)
            for key, value in xp_classes.items()
        )
    ):
        raise ValueError("Classes de récompense XP invalides.")
    named_catalog(data["story"], "Étapes du tutoriel")
    if set(data["story"]) != set(DEFAULTS["story"]):
        raise ValueError("Étapes du tutoriel incomplètes.")
    for value in data["story"].values():
        if (
            set(value) != {"name", "description"}
            or not isinstance(value["description"], str)
            or not 1 <= len(value["description"]) <= 2000
        ):
            raise ValueError("Description du tutoriel invalide.")
    return deepcopy(data)


def rare_drops(data):
    return {
        key: item["rare_chance"]
        for key, item in data["materials"].items()
        if item["rare_chance"] > 0
    }


def material_ids(mobs):
    result = set()
    for value in mobs.values():
        result.update(value.get("loot", {}))
        result.update(drop["item"] for drop in value.get("drops", []))
    return result


def validate_references(data, mobs, models):
    missing = material_ids(mobs) - set(data["materials"])
    if missing:
        raise ValueError(
            "Matériaux des mobs introuvables : " + ", ".join(sorted(missing))
        )
    classes = {item["id"]: item for item in models["classes"]}
    for identifier, control in data["summon_control"].items():
        model = classes.get(identifier)
        if (
            model is None
            or model["class_type"] != "INVOCATION"
            or control["energy"] not in {energy["type"] for energy in model["energies"]}
        ):
            raise ValueError(
                "Contrôle : classe d’invocation ou énergie introuvable : " + identifier
            )


def validate_start(data, maps):
    from . import tactics

    start = data["rules"]["start"]
    definition = maps.get(start["map"])
    position = [start["x"], start["y"]]
    if (
        definition is None
        or not tactics.walkable(definition, position)
        or position in definition.get("water", [])
        and position not in definition.get("bridges", [])
    ):
        raise ValueError("Apparition initiale : carte ou case impraticable.")
    if (
        not definition.get("exits")
        or tactics.path(definition, position, definition["exits"][0]["position"])
        is None
    ):
        raise ValueError("Apparition initiale : aucune sortie accessible.")
