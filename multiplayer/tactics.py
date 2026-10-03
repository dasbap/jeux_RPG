import math
from collections import deque
from copy import deepcopy

from . import forge, progression


LAYOUTS = (
    [(3, 2), (3, 3), (6, 5), (6, 6), (10, 7), (2, 6)],
    [(4, 1), (4, 2), (5, 5), (6, 5), (9, 7), (2, 6)],
    [(3, 4), (4, 4), (7, 2), (7, 3), (10, 6), (2, 6)],
)
PRESETS = {f"{zone}_{index + 1}": {"id": f"{zone}_{index + 1}", "name": f"{name} · terrain {index + 1}",
           "width": 14, "height": 10, "cell_metres": 2, "cover": [list(p) for p in layout]}
           for zone, name in (("clearing", "Clairière"), ("lisiere", "Lisière"), ("road", "Sentier"), ("rosee", "Entraînement"), ("brume", "Bois de Brume"))
           for index, layout in enumerate(LAYOUTS)}
CALL_TIME = 6.0
SEARCH_TIME = 180.0
MOVE_TIME = 1.2
GOBLIN_MOVE_TIME = 2.4


def distance(a, b):
    return math.dist(a, b)


def walkable(preset, position):
    return (isinstance(position, (list, tuple)) and len(position) == 2 and all(type(v) is int for v in position)
            and 0 <= position[0] < preset["width"] and 0 <= position[1] < preset["height"] and list(position) not in preset["cover"])


def path(preset, source, destination):
    if not walkable(preset, destination):
        return None
    queue = deque([(tuple(source), [])])
    seen = {tuple(source)}
    while queue:
        node, route = queue.popleft()
        if list(node) == list(destination):
            return route
        for point in ((node[0] + 1, node[1]), (node[0] - 1, node[1]), (node[0], node[1] + 1), (node[0], node[1] - 1)):
            if point not in seen and walkable(preset, point):
                seen.add(point)
                queue.append((point, route + [list(point)]))
    return None


def sight(preset, source, target):
    x, y = source
    tx, ty = target
    dx, dy = abs(tx - x), abs(ty - y)
    sx, sy = 1 if x < tx else -1, 1 if y < ty else -1
    error = dx - dy
    while (x, y) != (tx, ty):
        twice = error * 2
        if twice > -dy:
            error -= dy
            x += sx
        if twice < dx:
            error += dx
            y += sy
        if [x, y] in preset["cover"]:
            return False
    return True


def sees(preset, mob, unit):
    return distance(mob["position"], unit["position"]) <= (1.5 if unit.get("hidden") else 5) and sight(preset, mob["position"], unit["position"])


def begin(party, now, origin):
    from . import world
    zone = "road" if party["position"] in world.ROAD_POINTS else world.zone_of(party["position"])
    preset = PRESETS[f"{zone}_" + str(1 + (party.get("encounter_number", 1) - 1) % 3)]
    players = {key: {"position": [1, 6 + index], "hidden": origin == "explore", "route": [], "next_move": now}
               for index, key in enumerate(party["characters"])}
    party["battle"] = {"preset": preset["id"], "players": players, "corpses": [], "origin": origin, "next_brain": now}
    identifiers = [m["combat_id"] for m in party["mobs"]]
    for index, mob in enumerate(party["mobs"]):
        mob.update(position=[9 + index % 2, 2 + index], home=[9 + index % 2, 2 + index], state="patrol", target=None,
                   last_known=None, search_until=None, next_move=now + GOBLIN_MOVE_TIME, next_call=now, calling_until=None,
                   windup_until=None, known_dead=[], allies=[i for i in identifiers if i != mob["combat_id"]],
                   intent="Patrouille", stunned_until=0)
        if origin != "explore":
            mob["position"] = [4 + index % 2, 6 - index]
            mob["home"] = mob["position"][:]


def view(party, now):
    battle = party.get("battle")
    if not battle:
        return None
    preset = PRESETS[battle["preset"]]
    result = {**deepcopy(battle), "map": deepcopy(preset), "hostiles_alive": len(party["mobs"])}
    result["intents"] = [{"id": mob["combat_id"], "name": mob["name"], "action": mob["intent"],
                           "remaining_seconds": max(0, (mob.get("calling_until") or mob.get("windup_until") or mob.get("next_attack", now)) - now) / progression.RATIO}
                          for mob in party["mobs"]]
    return result


def allowed(party, player, target, attack_range):
    battle = party.get("battle")
    if not battle or player not in battle["players"]:
        return False
    unit = battle["players"][player]
    enemy = next((m for m in party["mobs"] if m["combat_id"] == target), None)
    other = enemy or battle["players"].get(target)
    return bool(other and distance(unit["position"], other["position"]) <= attack_range and sight(PRESETS[battle["preset"]], unit["position"], other["position"]))


def ready(party, player, now, error):
    from .tutorial import unpack
    actor = unpack(party["characters"][player])
    if not actor.is_alive() or actor.is_stunned():
        raise error("stunned" if actor.is_stunned() else "defeated", "Votre personnage ne peut pas agir.", 409)
    if party["ready"][player] > now:
        raise error("cooldown", "Attendez la fin du délai de 1,2 seconde.", 409)
    return actor


def execute(party, player, action, params, now, error):
    battle = party.get("battle")
    if not battle:
        raise error("not_fighting", "Aucun champ de bataille actif.", 409)
    actor = ready(party, player, now, error)
    unit = battle["players"][player]
    preset = PRESETS[battle["preset"]]
    if action == "battle_move":
        destination = [params["x"], params["y"]]
        route = params["path"]
        if not walkable(preset, destination) or not isinstance(route, list) or len(route) > preset["width"] * preset["height"] or not route or route[-1] != destination:
            raise error("invalid_path", "Trajet invalide.")
        previous = unit["position"]
        for point in route:
            if not walkable(preset, point) or abs(point[0] - previous[0]) + abs(point[1] - previous[1]) != 1:
                raise error("invalid_path", "Trajet bloqué ou vitesse impossible.")
            previous = point
        unit["route"] = deepcopy(route)
        unit["next_move"] = now + MOVE_TIME
        unit["hidden"] = False
        messages = [f"{actor.name} se déplace sur le champ de bataille."]
    elif action == "hide":
        if not any(distance(unit["position"], cover) <= 1.5 for cover in preset["cover"]):
            raise error("no_cover", "Rejoignez une couverture pour vous dissimuler.", 409)
        unit["route"] = []
        unit["hidden"] = True
        messages = [f"{actor.name} se cache derrière une couverture."]
    elif action == "harvest":
        corpse = next((c for c in battle["corpses"] if c["id"] == params["target"]), None)
        if not corpse or distance(unit["position"], corpse["position"]) > 1.5:
            raise error("too_far", "Approchez-vous du corps pour le dépecer.", 409)
        if corpse["harvested"]:
            raise error("already_harvested", "Vous avez déjà dépecé ce corps.", 409)
        for key in party["characters"]:
            for item, quantity in corpse["loot"].items():
                inventory = party["inventory"][key]
                inventory[item] = inventory.get(item, 0) + quantity
        corpse["harvested"].append(player)
        messages = [f"{actor.name} dépèce {corpse['name']} : " + ", ".join(f"{v} {k}" for k, v in corpse["loot"].items())]
    elif action == "leave_battle":
        if party["mobs"]:
            raise error("hostiles_alive", "Des ennemis sont encore présents.", 409)
        party["battle"] = None
        messages = ["Le groupe quitte le champ de bataille."]
    else:
        raise error("invalid_command", "Action tactique inconnue.")
    party["ready"][player] = now + progression.ACTION_SECONDS * progression.RATIO
    return messages


def damaged(party, mob, actor, now):
    battle = party["battle"]
    unit = battle["players"][actor]
    unit["hidden"] = False
    unit["route"] = []
    was_calling = mob["calling_until"] is not None
    mob["calling_until"] = None
    mob["next_call"] = now + CALL_TIME if was_calling else mob["next_call"]
    mob["needs_call"] = True
    if sees(PRESETS[battle["preset"]], mob, unit):
        mob["target"] = actor
        mob["last_known"] = unit["position"][:]
        mob["state"] = "chase"
    else:
        mob["state"] = "search"
        mob["search_until"] = now + SEARCH_TIME
    stun = max((e["duration"] for e in mob.get("effects", []) if e["group"] == "stun"), default=0)
    if stun:
        mob["stunned_until"] = now + stun * progression.ACTION_SECONDS * progression.RATIO
        mob["intent"] = "Étourdi : aucune action"


def defeated(party, mob, now, random, messages):
    from .tutorial import unpack, pack
    from . import world
    reward = 0 if party.get("training") else 50
    for key, data in party["characters"].items():
        character = unpack(data)
        if reward:
            character.gain_exp(reward)
        party["characters"][key] = pack(character)
    loot = {} if party.get("training") else dict(world.GOBLIN["loot"])
    if loot:
        for item, probability in forge.RARE_DROPS.items():
            if random() < probability:
                loot[item] = 1
    party["battle"]["corpses"].append({"id": mob["combat_id"], "name": mob["name"], "position": mob["position"][:], "loot": loot, "harvested": []})
    if party["quest"] == "active" and world.zone_of(party["position"]) == "lisiere":
        party["kills"] = min(3, party["kills"] + 1)
    messages.append(f"{mob['name']} vaincu : {reward} XP. Approchez-vous pour le dépecer.")
    if not party["mobs"] and party["combat_step"] == "first_fight":
        party["step"] = "road"


def advance(party, now, random):
    from .tutorial import unpack, pack, recover
    battle = party.get("battle")
    if not battle or now < battle.get("next_brain", 0):
        return []
    battle["next_brain"] = now + MOVE_TIME
    preset = PRESETS[battle["preset"]]
    messages = []
    characters = {key: unpack(data) for key, data in party["characters"].items()}
    for key, unit in battle["players"].items():
        actor = characters[key]
        if unit["route"] and actor.is_alive() and not actor.is_stunned() and unit["next_move"] <= now:
            unit["position"] = unit["route"].pop(0)
            unit["next_move"] = now + MOVE_TIME
    for mob in party["mobs"]:
        if mob.get("stunned_until", 0) > now:
            mob["calling_until"] = None
            mob["windup_until"] = None
            mob["intent"] = "Étourdi : aucune action"
            continue
        if mob.get("stunned_until"):
            mob["stunned_until"] = 0
            mob["effects"] = [e for e in mob["effects"] if e["group"] != "stun"]
            if not any(c.is_alive() and sees(preset, mob, battle["players"][key]) for key, c in characters.items()):
                mob.update(state="patrol", target=None, last_known=None, search_until=None, needs_call=False)
        for corpse in battle["corpses"]:
            if distance(mob["position"], corpse["position"]) <= 5 and sight(preset, mob["position"], corpse["position"]) and corpse["id"] not in mob["known_dead"]:
                mob["known_dead"].append(corpse["id"])
        visible = [(distance(mob["position"], unit["position"]), key) for key, unit in battle["players"].items()
                   if characters[key].is_alive() and sees(preset, mob, unit) and path(preset, mob["position"], unit["position"]) is not None]
        visible.sort()
        target = visible[0][1] if visible else None
        if target:
            previous = mob.get("target")
            mob["target"] = target
            mob["last_known"] = battle["players"][target]["position"][:]
            if mob["state"] == "patrol" or previous != target:
                mob["needs_call"] = True
            if mob.get("previous_distance", 0) <= 1.5 < visible[0][0]:
                mob["needs_call"] = True
            mob["previous_distance"] = visible[0][0]
            mob["state"] = "chase"
        elif mob.get("target"):
            mob["target"] = None
            mob["state"] = "search"
            mob["search_until"] = now + SEARCH_TIME
            mob["needs_call"] = True
            mob["windup_until"] = None
        if mob["calling_until"] is not None:
            mob["intent"] = "Appel aux alliés"
            if mob["calling_until"] <= now:
                mob["calling_until"] = None
                mob["next_call"] = now + CALL_TIME
                messages.append(f"{mob['name']} appelle ses alliés.")
                for ally in party["mobs"]:
                    if ally is not mob and distance(ally["position"], mob["position"]) <= 8:
                        ally["last_known"] = deepcopy(mob["last_known"])
                        ally["state"] = "search"
                        ally["search_until"] = now + SEARCH_TIME
            continue
        if mob.get("needs_call") and mob["next_call"] <= now and any(a not in mob["known_dead"] for a in mob["allies"]):
            mob["calling_until"] = now + CALL_TIME
            mob["needs_call"] = False
            mob["windup_until"] = None
            mob["intent"] = "Appel aux alliés"
            continue
        if target and visible[0][0] <= 1.5:
            if mob["windup_until"] is not None and mob["windup_until"] <= now:
                enemy = unpack(mob)
                actor = characters[target]
                actor.drop_xp = lambda killer: ""
                actor.lose_hp(enemy, 3)
                mob["windup_until"] = None
                mob["next_attack"] = now + 9 + random() * 6
                messages.append(f"{mob['name']} utilise Entaille contre {actor.name}.")
            elif mob["windup_until"] is None and mob["next_attack"] <= now:
                mob["windup_until"] = now + 1.8
            mob["intent"] = "Va utiliser Entaille" if mob["windup_until"] else "Prépare sa prochaine attaque"
        else:
            mob["windup_until"] = None
            destination = mob["last_known"] if mob["state"] == "search" else battle["players"][target]["position"] if target else None
            if mob["state"] == "search" and mob.get("search_until", now) <= now:
                mob.update(state="patrol", last_known=None, search_until=None)
                destination = None
            if mob["state"] == "search" and destination and distance(mob["position"], destination) < 1:
                candidates = [[destination[0] + dx, destination[1] + dy] for dx, dy in ((2, 0), (0, 2), (-2, 0), (0, -2))]
                candidates = [p for p in candidates if walkable(preset, p)]
                if candidates:
                    destination = candidates[int(now / 6) % len(candidates)]
            if destination is None:
                home = mob["home"]
                candidates = [[home[0] + dx, home[1] + dy] for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0))]
                candidates = [p for p in candidates if walkable(preset, p)]
                destination = candidates[int(now / 9 + int(mob["combat_id"].replace("mob", "").replace("-", "") or 1)) % len(candidates)]
            route = path(preset, mob["position"], destination)
            if route and mob["next_move"] <= now:
                mob["position"] = route[0]
                mob["next_move"] = now + GOBLIN_MOVE_TIME
            mob["intent"] = "Poursuit un joueur" if target else "Cherche à la dernière position connue" if mob["state"] == "search" else "Patrouille"
    party["characters"] = {key: pack(character) for key, character in characters.items()}
    if not any(c.is_alive() for c in characters.values()):
        party.update(mobs=[], mob=None, battle=None, journey=[], transit=None, position="rosee" if "rosee" in party["visited"] else "clearing")
        if party["step"] == "first_fight":
            party["step"] = "clearing"
        for key, character in characters.items():
            recover(character)
            party["characters"][key] = pack(character)
        messages.append("Le groupe est secouru et quitte le champ de bataille.")
    return messages
