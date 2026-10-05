from copy import deepcopy


RECIPES = {
    "casque": {"slot": "head", "name": "Casque de la lisière", "adjective": "raffiné", "cost": {"peau": 2, "croc": 1}, "hp": 3, "endurance": 1, "intelligence": 2, "sagesse": 1},
    "veste": {"slot": "torso", "name": "Veste de la lisière", "adjective": "solide", "cost": {"peau": 2, "croc": 3}, "hp": 10, "endurance": 3},
    "gants": {"slot": "hands", "name": "Gants de la lisière", "adjective": "précis", "cost": {"peau": 2, "croc": 2}, "hp": 2, "endurance": 1, "force": 2},
    "jambieres": {"slot": "legs", "name": "Jambières de la lisière", "adjective": "robustes", "cost": {"peau": 3, "croc": 2}, "hp": 5, "endurance": 2, "force": 1},
    "bottes": {"slot": "feet", "name": "Bottes de la lisière", "adjective": "agiles", "cost": {"peau": 2, "croc": 1}, "hp": 3, "endurance": 1, "sagesse": 1},
    "ceinture": {"slot": "waist", "name": "Ceinture de la lisière", "adjective": "renforcée", "cost": {"peau": 1, "croc": 2}, "hp": 2, "endurance": 1, "intelligence": 1, "sagesse": 2},
}
BONUS_STATS = ("hp", "endurance", "force", "intelligence", "sagesse")
RARE_DROPS = {"cristal_gobelin": .08, "noyau_gobelin": .02}


def upgrade_cost(recipe, level):
    definition = RECIPES[recipe]
    cost = {item: quantity * (level + 1) + level * level for item, quantity in definition["cost"].items()}
    if level >= 4:
        cost["cristal_gobelin"] = (level - 2) // 2
    if level >= 8:
        cost["noyau_gobelin"] = level - 7
    return cost


def piece(recipe, level=0):
    definition = RECIPES[recipe]
    return {"recipe": recipe, "slot": definition["slot"], "level": level,
            "name": definition["name"] + (" " + definition["adjective"] if level == 10 else ""),
            **{stat: definition.get(stat, 0) + (level * 2 if stat == "hp" else level // 2 if definition.get(stat, 0) else 0) for stat in BONUS_STATS}}


def migrate(party):
    for key, equipment in list(party["equipment"].items()):
        if isinstance(equipment, str):
            party["equipment"][key] = {"torso": piece("veste")}

    for key, equipment in party["equipment"].items():
        if not isinstance(equipment, dict):
            continue
        for slot, old in list(equipment.items()):
            if all(stat in old for stat in BONUS_STATS):
                continue
            new = piece(old["recipe"], old["level"])
            for stat in BONUS_STATS:
                delta = new[stat] - old.get(stat, 0)
                values = party["characters"][key]["stats"][stat]
                values["max"] += delta
                values["current"] = min(values["max"], values["current"] + delta) if stat == "hp" else values["current"] + delta
            equipment[slot] = new


def catalogue(party, player):
    migrate(party)
    gear = party["equipment"].get(player, {})
    inventory = party["inventory"][player]
    result = []
    for recipe, definition in RECIPES.items():
        equipped = gear.get(definition["slot"])
        cost = upgrade_cost(recipe, equipped["level"] + 1) if equipped and equipped["level"] < 10 else None if equipped else definition["cost"]
        result.append({**deepcopy(definition), "recipe": recipe, "equipped": deepcopy(equipped), "cost": cost,
                       "affordable": bool(cost is not None and all(inventory.get(k, 0) >= v for k, v in cost.items()))})
    return result


def execute(party, player, action, recipe, error):
    from .tutorial import unpack, pack
    if party["quest"] != "completed":
        raise error("forge_locked", "Forge verrouillée : terminez et rendez la quête de Mira.", 409)
    if party["position"] != "forge" or party.get("battle") or party.get("transit"):
        raise error("wrong_location", "Rejoignez la forge hors combat pour fabriquer ou améliorer une pièce.", 409)
    if not isinstance(recipe, str) or recipe not in RECIPES:
        raise error("invalid_recipe", "Recette inconnue.")
    migrate(party)
    gear = party["equipment"].setdefault(player, {})
    slot = RECIPES[recipe]["slot"]
    old = gear.get(slot)
    if action == "craft" and old:
        raise error("already_crafted", "Cette pièce est déjà équipée.", 409)
    if action == "upgrade" and (not old or old["recipe"] != recipe):
        raise error("missing_equipment", "Fabriquez cette pièce avant de l'améliorer.", 409)
    if old and old["level"] >= 10:
        raise error("max_upgrade", "Cette pièce a atteint +10.", 409)
    level = old["level"] + 1 if old else 0
    cost = upgrade_cost(recipe, level) if old else RECIPES[recipe]["cost"]
    inventory = party["inventory"][player]
    if any(inventory.get(item, 0) < quantity for item, quantity in cost.items()):
        raise error("missing_materials", "Matériaux insuffisants pour cette amélioration.", 409)
    for item, quantity in cost.items():
        inventory[item] -= quantity
    new = piece(recipe, level)
    actor = unpack(party["characters"][player])
    for name in BONUS_STATS:
        delta = new[name] - (old.get(name, 0) if old else 0)
        stat = getattr(actor, name)
        stat.value += delta
        stat.current_value = min(stat.value, stat.current_value + delta) if name == "hp" else stat.current_value + delta
    gear[slot] = new
    party["characters"][player] = pack(actor)
    from . import content, world
    if action == "craft":
        from . import achievements
        achievements.event(party, "craft", recipe)
        content.quest_event(party, "craft", recipe, world.zone_of(party["position"]))
    previous_step = party["step"]
    if party["step"] == "craft" and all("torso" in party["equipment"].get(key, {}) for key in party["characters"]):
        party["step"] = "travel"
    messages = [f"{actor.name} {'améliore' if old else 'fabrique et équipe'} {new['name']} +{level}."]
    if previous_step == "craft" and party["step"] == "travel":
        messages.append("Objectif accompli : veste fabriquée et équipée. Prochaine étape : rejoindre le village de Brume.")
    elif previous_step == "craft" and slot == "torso":
        messages.append(f"{actor.name} a terminé la fabrication de sa veste. Attendez que les autres joueurs équipent la leur.")
    return messages, False
