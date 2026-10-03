from copy import deepcopy


RECIPES = {
    "casque": {"slot": "head", "name": "Casque de la lisière", "adjective": "raffiné", "cost": {"peau": 2, "croc": 1}, "hp": 3, "endurance": 1},
    "veste": {"slot": "torso", "name": "Veste de la lisière", "adjective": "solide", "cost": {"peau": 2, "croc": 3}, "hp": 10, "endurance": 3},
    "gants": {"slot": "hands", "name": "Gants de la lisière", "adjective": "précis", "cost": {"peau": 2, "croc": 2}, "hp": 2, "endurance": 1},
    "jambieres": {"slot": "legs", "name": "Jambières de la lisière", "adjective": "robustes", "cost": {"peau": 3, "croc": 2}, "hp": 5, "endurance": 2},
    "bottes": {"slot": "feet", "name": "Bottes de la lisière", "adjective": "agiles", "cost": {"peau": 2, "croc": 1}, "hp": 3, "endurance": 1},
    "ceinture": {"slot": "waist", "name": "Ceinture de la lisière", "adjective": "renforcée", "cost": {"peau": 1, "croc": 2}, "hp": 2, "endurance": 1},
}
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
            "hp": definition["hp"] + level * 2, "endurance": definition["endurance"] + level // 2}


def migrate(party):
    for key, equipment in list(party["equipment"].items()):
        if isinstance(equipment, str):
            party["equipment"][key] = {"torso": piece("veste")}


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
    hp_delta = new["hp"] - (old["hp"] if old else 0)
    endurance_delta = new["endurance"] - (old["endurance"] if old else 0)
    actor.hp.value += hp_delta
    actor.hp.current_value = min(actor.hp.value, actor.hp.current_value + hp_delta)
    actor.endurance.value += endurance_delta
    actor.endurance.current_value += endurance_delta
    gear[slot] = new
    party["characters"][player] = pack(actor)
    if party["step"] == "craft" and all("torso" in party["equipment"].get(key, {}) for key in party["characters"]):
        party["step"] = "travel"
    return [f"{actor.name} {'améliore' if old else 'fabrique et équipe'} {new['name']} +{level}."], False
