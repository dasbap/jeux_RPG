from copy import deepcopy

from .content import DATA
from .gameplay_catalog import rare_drops

GAMEPLAY = DATA["gameplay"]
RECIPES = GAMEPLAY["recipes"]
BONUS_STATS = ("hp", "endurance", "force", "intelligence", "sagesse")
RARE_DROPS = rare_drops(GAMEPLAY)
RULES = GAMEPLAY["rules"]["forge"]


def recipe_settings(recipe, gameplay):
    selected = gameplay or GAMEPLAY
    return selected["recipes"][recipe], selected["rules"]["forge"], selected


def upgrade_cost(recipe, level, gameplay=None):
    definition, rules, gameplay = recipe_settings(recipe, gameplay)
    cost = {
        item: quantity * (1 + level * rules["cost_linear"])
        + level * level * rules["cost_quadratic"]
        for item, quantity in definition["cost"].items()
    }
    for extra in gameplay["rare_costs"]:
        if level >= extra["start_level"]:
            cost[extra["item"]] = (
                cost.get(extra["item"], 0)
                + (level - extra["offset"]) // extra["divisor"]
            )
    return cost


def piece(recipe, level=0, gameplay=None):
    definition, rules, _ = recipe_settings(recipe, gameplay)
    return {
        "recipe": recipe,
        "slot": definition["slot"],
        "level": level,
        "name": definition["name"]
        + (" " + definition["adjective"] if level >= rules["max_level"] else ""),
        **{
            stat: definition.get(stat, 0)
            + (
                level * rules["hp_per_level"]
                if stat == "hp"
                else level // rules["stat_every_levels"]
                if definition.get(stat, 0)
                else 0
            )
            for stat in BONUS_STATS
        },
    }


def migrate(party):
    for key, equipment in list(party["equipment"].items()):
        if isinstance(equipment, str):
            party["equipment"][key] = {"torso": piece("veste")}

    for key, equipment in party["equipment"].items():
        if not isinstance(equipment, dict):
            continue
        for slot, old in list(equipment.items()):
            if old.get("recipe") not in RECIPES:
                continue
            new = piece(old["recipe"], old["level"])
            new["slot"] = slot
            if new == old:
                continue
            for stat in BONUS_STATS:
                delta = new[stat] - old.get(stat, 0)
                values = party["characters"][key]["stats"][stat]
                values["max"] += delta
                values["current"] = (
                    max(0, min(values["max"], values["current"] + delta))
                    if stat == "hp"
                    else values["current"] + delta
                )
            equipment[slot] = new


def catalogue(party, player):
    migrate(party)
    gear = party["equipment"].get(player, {})
    inventory = party["inventory"][player]
    result = []
    for recipe, definition in RECIPES.items():
        equipped = next(
            (item for item in gear.values() if item["recipe"] == recipe), None
        )
        cost = (
            upgrade_cost(recipe, equipped["level"] + 1)
            if equipped and equipped["level"] < RULES["max_level"]
            else None
            if equipped
            else definition["cost"]
        )
        result.append(
            {
                **deepcopy(definition),
                "recipe": recipe,
                "max_level": RULES["max_level"],
                "equipped": deepcopy(equipped),
                "cost": cost,
                "affordable": bool(
                    cost is not None
                    and all(inventory.get(k, 0) >= v for k, v in cost.items())
                ),
            }
        )
    return result


def execute(party, player, action, recipe, error):
    from .tutorial import pack, unpack

    if party["position"] != "forge" or party.get("battle") or party.get("transit"):
        raise error(
            "wrong_location",
            "Rejoignez la forge hors combat pour fabriquer ou améliorer une pièce.",
            409,
        )
    if not isinstance(recipe, str) or recipe not in RECIPES:
        raise error("invalid_recipe", "Recette inconnue.")
    migrate(party)
    gear = party["equipment"].setdefault(player, {})
    slot = RECIPES[recipe]["slot"]
    existing = next(
        ((place, item) for place, item in gear.items() if item["recipe"] == recipe),
        None,
    )
    if action == "upgrade" and existing:
        slot = existing[0]
    old = gear.get(slot)
    if action == "craft" and existing:
        raise error("already_crafted", "Cette pièce est déjà équipée.", 409)
    if action == "upgrade" and (not old or old["recipe"] != recipe):
        raise error(
            "missing_equipment", "Fabriquez cette pièce avant de l'améliorer.", 409
        )
    if action == "upgrade" and old and old["level"] >= RULES["max_level"]:
        raise error("max_upgrade", f"Cette pièce a atteint +{RULES['max_level']}.", 409)
    level = old["level"] + 1 if action == "upgrade" else 0
    cost = (
        upgrade_cost(recipe, level) if action == "upgrade" else RECIPES[recipe]["cost"]
    )
    inventory = party["inventory"][player]
    if any(inventory.get(item, 0) < quantity for item, quantity in cost.items()):
        raise error(
            "missing_materials", "Matériaux insuffisants pour cette amélioration.", 409
        )
    for item, quantity in cost.items():
        inventory[item] -= quantity
    new = piece(recipe, level)
    new["slot"] = slot
    actor = unpack(party["characters"][player])
    for name in BONUS_STATS:
        delta = new[name] - (old.get(name, 0) if old else 0)
        stat = getattr(actor, name)
        stat.value += delta
        stat.current_value = (
            max(0, min(stat.value, stat.current_value + delta))
            if name == "hp"
            else stat.current_value + delta
        )
    gear[slot] = new
    party["characters"][player] = pack(actor)
    from . import content, world

    if action == "craft":
        from . import achievements

        achievements.event(party, "craft", recipe)
        content.quest_event(party, "craft", recipe, world.zone_of(party["position"]))
        content.endgame_event(party, "craft", recipe, world.zone_of(party["position"]))
    previous_step = party["step"]
    if party["step"] == "craft" and all(
        "torso" in party["equipment"].get(key, {}) for key in party["characters"]
    ):
        party["step"] = "travel"
    messages = [
        f"{actor.name} {'améliore' if action == 'upgrade' else 'fabrique et équipe'} {new['name']} +{level}."
    ]
    if previous_step == "craft" and party["step"] == "travel":
        messages.append(
            "Objectif accompli : veste fabriquée et équipée. Prochaine étape : rejoindre le village de Brume."
        )
    elif previous_step == "craft" and slot == "torso":
        messages.append(
            f"{actor.name} a terminé la fabrication de sa veste. Attendez que les autres joueurs équipent la leur."
        )
    return messages, False
