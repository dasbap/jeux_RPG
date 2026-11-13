from copy import deepcopy

from .content import DATA
from .gameplay_catalog import rare_drops

GAMEPLAY = DATA["gameplay"]
RECIPES = GAMEPLAY["recipes"]
BONUS_STATS = ("hp", "endurance", "force", "intelligence", "sagesse")
RARE_DROPS = rare_drops(GAMEPLAY)
RULES = GAMEPLAY["rules"]["forge"]


def rosee_unlock_quest():
    from . import content

    quests = content.DATA["quests"]
    original = next(
        (
            quest
            for quest in quests
            if quest["id"] == "mira_hunt"
            or "mira_hunt" in quest.get("previous_ids", [])
        ),
        None,
    )
    return original or next((quest for quest in quests if content.is_hunt(quest)), None)


def rosee_unlocked(party, player=None):
    from . import content

    quest = rosee_unlock_quest()
    from . import narrative

    if player is not None and narrative.enabled():
        return quest is None or narrative.completed(party, player, quest["id"])
    return (
        quest is None
        or content.quest_states(party).get(quest["id"], {}).get("status") == "completed"
    )


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
        **({"set_id": definition["set_id"]} if definition.get("set_id") else {}),
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


def set_catalogue(equipment, gameplay=None):
    selected = GAMEPLAY if gameplay is None else gameplay
    recipes = RECIPES if gameplay is None else selected["recipes"]
    result = []
    for identifier, definition in selected.get("equipment_sets", {}).items():
        slots = {
            recipes[item["recipe"]]["slot"]
            for item in equipment.values()
            if isinstance(item, dict)
            and item.get("recipe") in recipes
            and recipes[item["recipe"]].get("set_id") == identifier
        }
        if not slots:
            continue
        tiers = [
            {
                "pieces": int(count),
                "active": len(slots) >= int(count),
                "bonuses": deepcopy(bonuses),
            }
            for count, bonuses in sorted(
                definition["bonuses"].items(), key=lambda item: int(item[0])
            )
        ]
        bonuses = {
            stat: sum(tier["bonuses"].get(stat, 0) for tier in tiers if tier["active"])
            for stat in BONUS_STATS
        }
        result.append(
            {
                "id": identifier,
                "name": definition["name"],
                "pieces": len(slots),
                "tiers": tiers,
                "bonuses": bonuses,
            }
        )
    return result


def sync_set_bonuses(party):
    applied = party.setdefault("equipment_set_bonuses", {})
    for player, character in party["characters"].items():
        equipment = party.get("equipment", {}).get(player, {})
        sets = set_catalogue(equipment if isinstance(equipment, dict) else {})
        wanted = {
            stat: sum(item["bonuses"][stat] for item in sets) for stat in BONUS_STATS
        }
        previous = applied.get(player, {})
        for stat in BONUS_STATS:
            delta = wanted[stat] - previous.get(stat, 0)
            if not delta:
                continue
            values = character["stats"][stat]
            alive = values["current"] > 0
            values["max"] += delta
            values["current"] = (
                (max(0, min(values["max"], values["current"] + delta)) if alive else 0)
                if stat == "hp"
                else values["current"] + delta
            )
        applied[player] = wanted


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
    sync_set_bonuses(party)


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
                "set_name": GAMEPLAY.get("equipment_sets", {})
                .get(definition.get("set_id"), {})
                .get("name"),
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
    if not rosee_unlocked(party, player):
        quest = rosee_unlock_quest()
        raise error(
            "forge_locked",
            f"La forge de Rosée se débloque en terminant la quête « {quest['name']} » auprès de Mira.",
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
    sync_set_bonuses(party)
    from . import content, world

    if action == "craft":
        from . import achievements

        achievements.event(party, "craft", recipe)
        content.quest_event(
            party, "craft", recipe, world.zone_of(party["position"]), player=player
        )
        content.endgame_event(party, "craft", recipe, world.zone_of(party["position"]))
    elif action == "upgrade":
        from . import content, world

        content.quest_event(
            party,
            "upgrade",
            recipe,
            world.zone_of(party["position"]),
            level=level,
            player=player,
        )
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
