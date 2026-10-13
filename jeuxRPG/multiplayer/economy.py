from copy import deepcopy

from . import content


def catalogue():
    return deepcopy(content.DATA.get("economy", []))


def prices():
    return {item["id"]: item for item in content.DATA.get("economy", [])}


def migrate(party):
    gold = party.setdefault("gold", {})
    for player in party.get("characters", {}):
        gold.setdefault(player, content.WORLD.get("starting_gold", 0))


def execute(party, player, merchant, action, item, quantity, error):
    migrate(party)
    if not merchant or not merchant.get("merchant"):
        raise error("not_merchant", "Ce PNJ ne propose pas de commerce.", 409)
    if type(quantity) is not int or not 1 <= quantity <= content.WORLD.get(
        "trade_max_quantity", 999
    ):
        raise error("invalid_quantity", "Quantité d’échange invalide.")
    definition = prices().get(item)
    if definition is None:
        raise error("unknown_item", "Ce matériau n’est pas coté.")
    inventory = party["inventory"][player]
    if action == "buy":
        total = definition["buy"] * quantity
        if party["gold"][player] < total:
            raise error("missing_gold", "Or insuffisant.", 409)
        party["gold"][player] -= total
        inventory[item] = inventory.get(item, 0) + quantity
        return [f"Achat : {quantity} {definition['name']} pour {total} or."]
    if action == "sell":
        if inventory.get(item, 0) < quantity:
            raise error("missing_materials", "Matériaux insuffisants.", 409)
        total = definition["sell"] * quantity
        inventory[item] -= quantity
        party["gold"][player] += total
        return [f"Vente : {quantity} {definition['name']} pour {total} or."]
    raise error("invalid_command", "Action économique inconnue.")
