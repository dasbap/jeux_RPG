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


def class_labels(definition):
    names = {
        item["id"]: item["name"]
        for item in [
            *DATA.get("templates", {}).get("classes", []),
            *DATA.get("classes", []),
        ]
    }
    return [names.get(key, key) for key in definition.get("classes", [])]


def compatibility_reason(party, player, recipe):
    definition = RECIPES[recipe]
    allowed = definition.get("classes")
    if allowed and party["characters"][player]["class_name"] not in allowed:
        return "Classes autoris\u00e9es : " + ", ".join(class_labels(definition)) + "."
    return ""


def piece(recipe, level=0, gameplay=None):
    definition, rules, _ = recipe_settings(recipe, gameplay)
    return {
        "recipe": recipe,
        **(
            {
                "classes": definition["classes"][:],
                "class_names": class_labels(definition),
            }
            if definition.get("classes")
            else {}
        ),
        **(
            {"weapon_type": definition["weapon_type"]}
            if definition.get("weapon_type")
            else {}
        ),
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


def set_catalogue(equipment, gameplay=None, *, include_inactive=False):
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
        if not slots and not include_inactive:
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
    storage = party.setdefault("stored_equipment", {})
    for player in party["characters"]:
        bag = storage.setdefault(player, {})
        for recipe, old in list(bag.items()):
            if recipe in RECIPES:
                bag[recipe] = piece(recipe, old["level"])
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
    # Builder edits can revoke a class: keep the item, remove its bonuses once.
    for player, equipment in party["equipment"].items():
        if not isinstance(equipment, dict):
            continue
        for slot, item in list(equipment.items()):
            if item.get("recipe") not in RECIPES or not compatibility_reason(
                party, player, item["recipe"]
            ):
                continue
            for stat in BONUS_STATS:
                values = party["characters"][player]["stats"][stat]
                values["max"] -= item.get(stat, 0)
                values["current"] = (
                    min(values["current"], values["max"])
                    if stat == "hp"
                    else values["current"] - item.get(stat, 0)
                )
            storage.setdefault(player, {})[item["recipe"]] = equipment.pop(slot)
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
        owned = equipped or party["stored_equipment"].get(player, {}).get(recipe)
        cost = (
            upgrade_cost(recipe, owned["level"] + 1)
            if owned and owned["level"] < RULES["max_level"]
            else None
            if owned
            else definition["cost"]
        )
        result.append(
            {
                **deepcopy(definition),
                "recipe": recipe,
                "class_names": class_labels(definition),
                "compatible": not compatibility_reason(party, player, recipe),
                "compatibility_reason": compatibility_reason(party, player, recipe),
                "set_name": GAMEPLAY.get("equipment_sets", {})
                .get(definition.get("set_id"), {})
                .get("name"),
                "max_level": RULES["max_level"],
                "equipped": deepcopy(equipped),
                "owned": deepcopy(owned),
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
    reason = compatibility_reason(party, player, recipe)
    if reason:
        raise error("incompatible_class", reason, 409)
    migrate(party)
    gear = party["equipment"].setdefault(player, {})
    slot = RECIPES[recipe]["slot"]
    existing = next(
        ((place, item) for place, item in gear.items() if item["recipe"] == recipe),
        None,
    )
    bag = party["stored_equipment"].setdefault(player, {})
    stored = bag.get(recipe)
    if action == "upgrade" and existing:
        slot = existing[0]
    old = stored if action == "upgrade" and stored else gear.get(slot)
    if action == "craft" and existing:
        raise error("already_crafted", "Cette pièce est déjà équipée.", 409)
    if action == "craft" and stored:
        raise error(
            "already_crafted",
            "Cette pièce est déjà possédée. Équipez-la depuis votre équipement.",
            409,
        )
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
    for name in BONUS_STATS if not (stored and action == "upgrade") else ():
        delta = new[name] - (old.get(name, 0) if old else 0)
        stat = getattr(actor, name)
        stat.value += delta
        stat.current_value = (
            max(0, min(stat.value, stat.current_value + delta))
            if name == "hp"
            else stat.current_value + delta
        )
    if stored and action == "upgrade":
        bag[recipe] = new
    else:
        if old and old["recipe"] != recipe:
            bag[old["recipe"]] = deepcopy(old)
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


def equipment_lock_reason(party, player):
    from . import mob_rules

    character = party["characters"][player]
    battle = party.get("battle")
    unit = battle.get("players", {}).get(player, {}) if battle else {}
    fighting = battle and (
        not party.get("field_map")
        or any(
            mob_rules.is_hostile(mob) and mob.get("alerted")
            for mob in party.get("mobs", [])
        )
    )
    if (
        party.get("transit")
        or fighting
        or unit.get("casting")
        or character["stats"]["hp"]["current"] <= 0
    ):
        return "Changez votre équipement à l’arrêt, vivant et hors combat."
    return ""


def change_equipment(party, player, action, recipe, error):
    """Move owned gear between a slot and storage without granting healing."""
    reason = equipment_lock_reason(party, player)
    if reason:
        raise error("equipment_unavailable", reason, 409)
    if not isinstance(recipe, str) or recipe not in RECIPES:
        raise error("invalid_recipe", "Pièce inconnue.")
    if action == "equip" and (reason := compatibility_reason(party, player, recipe)):
        raise error("incompatible_class", reason, 409)
    migrate(party)
    character = party["characters"][player]
    gear = party["equipment"].setdefault(player, {})
    bag = party["stored_equipment"].setdefault(player, {})
    worn_slot = next(
        (slot for slot, item in gear.items() if item["recipe"] == recipe), None
    )
    if action == "unequip":
        if worn_slot is None:
            raise error("missing_equipment", "Cette pièce n’est pas équipée.", 409)
        slot, new = worn_slot, None
    else:
        if recipe not in bag:
            raise error(
                "missing_equipment",
                "Vous ne possédez pas cette pièce dans votre réserve.",
                409,
            )
        slot, new = RECIPES[recipe]["slot"], bag[recipe]
    old = gear.get(slot)
    hp = character["stats"]["hp"]["current"]
    for stat in BONUS_STATS:
        delta = (new.get(stat, 0) if new else 0) - (old.get(stat, 0) if old else 0)
        values = character["stats"][stat]
        values["max"] += delta
        values["current"] += delta if stat != "hp" else 0
    if new:
        bag.pop(recipe)
        gear[slot] = new
    else:
        gear.pop(slot)
    if old:
        bag[old["recipe"]] = old
    sync_set_bonuses(party)
    character["stats"]["hp"]["current"] = min(hp, character["stats"]["hp"]["max"])
    item = new or old
    return [
        f"{character['name']} {'équipe' if new else 'retire'} {item['name']} +{item['level']}."
    ], False
