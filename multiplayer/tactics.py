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
SEARCH_TIME = 10 * progression.RATIO
MOVE_TIME = 1.2
GOBLIN_MOVE_TIME = 2.4
CONTROL_RULES = {"Squelette": {"energy": "Mana", "per_second": .4}}


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
    return distance(mob["position"], unit["position"]) <= (1.5 if unit.get("hidden") else 6) and sight(preset, mob["position"], unit["position"])


def begin(party, now, origin):
    from . import world
    zone = "road" if party["position"] in world.ROAD_POINTS else world.zone_of(party["position"])
    preset = PRESETS[f"{zone}_" + str(1 + (party.get("encounter_number", 1) - 1) % 3)]
    players = {key: {"position": [1, 6 + index], "hidden": origin == "explore", "route": [], "next_move": now}
               for index, key in enumerate(party["characters"])}
    party["battle"] = {"preset": preset["id"], "players": players, "corpses": [], "origin": origin, "next_brain": now}
    occupied = [u["position"] for u in players.values()]
    identifiers = [m["combat_id"] for m in party["mobs"]]
    for index, mob in enumerate(party["mobs"]):
        mob.update(position=[9 + index % 2, 2 + index], home=[9 + index % 2, 2 + index], state="patrol", target=None,
                   last_known=None, search_until=None, next_move=now + GOBLIN_MOVE_TIME, next_call=now, calling_until=None,
                   windup_until=None, known_dead=[], allies=[i for i in identifiers if i != mob["combat_id"]],
                   intent="Patrouille", stunned_until=0)
        if origin != "explore":
            mob["position"] = [4 + index % 2, 6 - index]
            mob["home"] = mob["position"][:]

        mob["position"] = free_position(preset, mob["position"], occupied)
        occupied.append(mob["position"])
        mob["home"] = mob["position"][:]
        mob["patrol_route"] = patrol_route(preset, index)
        mob["patrol_index"] = 0
    sync_summons(party, now)


def free_position(preset, wanted, occupied=()):
    cells = [[x, y] for x in range(preset["width"]) for y in range(preset["height"])
             if walkable(preset, [x, y]) and [x, y] not in occupied]
    return min(cells, key=lambda p: (distance(p, wanted), p[1], p[0]))


def patrol_route(preset, index):
    wanted = ((8, 1), (12, 1), (12, 8), (8, 8), (4, 8), (4, 4))
    route = [free_position(preset, list(p)) for p in wanted]
    offset = index % len(route)
    return route[offset:] + route[:offset]


def cast_view(party, player, now):
    cast = party.get("battle") and party["battle"]["players"][player].get("casting")
    return {"name": cast["skill_name"], "remaining_seconds": max(0, cast["ends_at"] - now) / progression.RATIO,
            "concentration": cast["concentration"]} if cast else None


def complete_casts(party, now, random):
    from .tutorial import execute_one, unpack
    from .service import GameError
    if not party.get("battle"):
        return []
    messages = []
    for key, unit in party["battle"]["players"].items():
        cast = unit.get("casting")
        if not cast:
            continue
        actor = unpack(party["characters"][key])
        if not actor.is_alive() or actor.is_stunned():
            unit.pop("casting", None)
            messages.append(f"{actor.name} : incantation interrompue.")
        elif cast["ends_at"] <= now:
            unit.pop("casting", None)
            try:
                result, _ = execute_one(party, key, "skill", {"skill_name": cast["skill_name"], "target": cast["target"]}, now, GameError, random, resolved=True)
                messages.extend(result)
            except GameError:
                messages.append(f"{actor.name} : {cast['skill_name']} annulé, cible devenue inaccessible.")
    return messages


def sync_summons(party, now):
    battle = party.get("battle")
    if not battle:
        return
    summons = battle.setdefault("summons", {})
    active = set()
    reserved = {i["id"] for data in party["characters"].values() for i in data["invocations"] if i["id"] != "-1"}
    occupied = [p["position"] for p in battle["players"].values()] + [m["position"] for m in party["mobs"]]
    for owner, data in party["characters"].items():
        for index, invocation in enumerate(data["invocations"]):
            if invocation["id"] == "-1":
                sequence = battle.get("summon_sequence", 0)
                key = f"{owner}:summon:{sequence}"
                while key in summons or key in reserved:
                    sequence += 1
                    key = f"{owner}:summon:{sequence}"
                battle["summon_sequence"] = sequence + 1
                invocation["id"] = key
                reserved.add(key)
            key = invocation["id"]
            active.add(key)
            if key not in summons:
                summons[key] = {"owner": owner, "index": index, "position": free_position(PRESETS[battle["preset"]], battle["players"][owner]["position"], occupied),
                                "next_move": now, "next_attack": now, "hidden": False, "route": []}
                occupied.append(summons[key]["position"])
            summons[key].update(index=index, name=invocation["name"], hp=invocation["stats"]["hp"]["current"], max_hp=invocation["stats"]["hp"]["max"],
                                stats=deepcopy(invocation["stats"]), energies=deepcopy(invocation["energies"]), effects=deepcopy(invocation["effects"]),
                                control_cost=deepcopy(CONTROL_RULES.get(invocation["class_name"], {"energy": None, "per_second": 0})))
            from .tutorial import unpack
            actor = unpack(invocation)
            summons[key]["skills"] = [{"name": skill.name, "description": skill.description,
                "cost": skill.energie_cost, "energy": skill.energie_target.__name__,
                "range": progression.attack_range(actor, skill), "cast_seconds": progression.casting(skill)["seconds"],
                "cooldown": max(0, summons[key].get("skill_ready", {}).get(skill.name, 0) - now) / progression.RATIO,
                "available": skill.can_afford(actor) and summons[key].get("skill_ready", {}).get(skill.name, 0) <= now,
                "type": skill.skill_type.name} for skill in actor.skills.values()]
    battle["summons"] = {key: unit for key, unit in summons.items() if key in active}


def advance_summons(party, characters, now, random, messages):
    from .tutorial import unpack, pack, sync_mobs
    battle = party["battle"]
    preset = PRESETS[battle["preset"]]
    for summon_id, unit in battle.get("summons", {}).items():
        if not characters[unit["owner"]].is_alive():
            continue
        invocations = characters[unit["owner"]].invocations.get_all()
        if unit["index"] >= len(invocations) or not invocations[unit["index"]].is_alive() or invocations[unit["index"]].is_stunned():
            continue
        invocation = invocations[unit["index"]]
        cast = unit.get("casting")
        if cast:
            if cast["ends_at"] > now:
                continue
            unit.pop("casting", None)
            skill = invocation.skills.get(cast["skill_name"])
            target = next((mob for mob in party["mobs"] if mob["combat_id"] == cast["target"]), None)
            if not target or not visible(party, unit["owner"], target) or distance(unit["position"], target["position"]) > progression.attack_range(invocation, skill) or not sight(preset, unit["position"], target["position"]):
                messages.append(f"{invocation.name} : cible perdue pendant l’incantation.")
                continue
            enemy = unpack(target)
            enemy.drop_xp = lambda killer: ""
            invocation.get_energie(skill.energie_target).current_value += skill.energie_cost
            skill.current_cooldown = 0
            progression.scale_skill(invocation, skill)
            success, _ = invocation.use_skill(skill.name, enemy)
            target.update(pack(enemy))
            if success:
                damaged(party, target, summon_id, now)
                messages.append(f"{invocation.name} utilise {skill.name}.")
                if not enemy.is_alive():
                    party["mobs"].remove(target)
                    party["characters"] = {key: pack(c) for key, c in characters.items()}
                    defeated(party, target, now, random, messages)
                    for key, data in party["characters"].items():
                        characters[key] = unpack(data)
                    sync_mobs(party)
            continue
        if unit.get("controlled"):
            order = unit.get("order", {"type": "hold"})
            if order["type"] == "move":
                if unit["route"] and unit["next_move"] <= now:
                    unit["position"] = unit["route"].pop(0)
                    unit["next_move"] = now + MOVE_TIME
                continue
            if order["type"] != "attack":
                continue
            candidates = [mob for mob in party["mobs"] if mob["combat_id"] == order["target"] and visible(party, unit["owner"], mob)]
        else:
            candidates = [mob for mob in party["mobs"] if distance(unit["position"], mob["position"]) <= 6 and sight(preset, unit["position"], mob["position"])]
        if not candidates:
            continue
        target = min(candidates, key=lambda m: (distance(unit["position"], m["position"]), m["stats"]["hp"]["current"], m["combat_id"]))
        if distance(unit["position"], target["position"]) <= 1.5 and sight(preset, unit["position"], target["position"]):
            if unit["next_attack"] > now:
                continue
            enemy = unpack(target)
            enemy.drop_xp = lambda killer: ""
            enemy.lose_hp(invocation, progression.simple_damage(invocation))
            target.update(pack(enemy))
            damaged(party, target, summon_id, now)
            unit["next_attack"] = now + 3 * progression.RATIO
            messages.append(f"{invocation.name} attaque {target['name']}.")
            if not enemy.is_alive():
                party["mobs"].remove(target)
                party["characters"] = {key: pack(c) for key, c in characters.items()}
                defeated(party, target, now, random, messages)
                for key, data in party["characters"].items():
                    characters[key] = unpack(data)
                sync_mobs(party)
        elif unit["next_move"] <= now:
            route = path(preset, unit["position"], target["position"])
            if route:
                unit["position"] = route[0]
                unit["next_move"] = now + MOVE_TIME


def release_control(unit):
    unit.update(controlled=False, order=None, route=[])


def charge_control(party, characters, now, messages):
    for owner, character in characters.items():
        units = [u for u in party["battle"].get("summons", {}).values() if u["owner"] == owner and u.get("controlled")]
        if not units:
            continue
        totals = {}
        for unit in units:
            cost = unit["control_cost"]
            if cost["per_second"]:
                elapsed = max(0, now - unit.get("control_at", now)) / progression.RATIO
                totals[cost["energy"]] = totals.get(cost["energy"], 0) + elapsed * cost["per_second"]
            unit["control_at"] = now
        energies = {type(e).__name__: e for e in character.energie}
        credits = party.setdefault("control_credit", {}).setdefault(owner, {})
        fees = {key: max(0, math.ceil(amount - credits.get(key, 0) - 1e-9)) for key, amount in totals.items()}
        exhausted = not character.is_alive() or character.is_stunned() or any(key not in energies or energies[key].current_value < fee for key, fee in fees.items())
        for key, amount in totals.items():
            if key in energies:
                paid = min(energies[key].current_value, fees[key])
                energies[key].current_value -= paid
                credits[key] = max(0, round(credits.get(key, 0) + paid - amount, 6))
        if exhausted:
            for unit in units:
                release_control(unit)
            messages.append(f"{character.name} : contrôle interrompu, les alliés reprennent leur autonomie.")


def control(party, player, action, params, now, error):
    from .tutorial import unpack, pack
    battle = party.get("battle")
    if not battle:
        raise error("not_fighting", "Aucun champ de bataille actif.", 409)
    sync_summons(party, now)
    ids = params["units"]
    if not isinstance(ids, list) or len(ids) > len(battle["summons"]) or any(not isinstance(key, str) for key in ids) or len(set(ids)) != len(ids):
        raise error("invalid_units", "Sélection d’alliés invalide.")
    units = [battle["summons"].get(key) for key in ids]
    if any(not unit or unit["owner"] != player or unit["hp"] <= 0 for unit in units):
        raise error("forbidden_unit", "Vous ne pouvez contrôler que vos alliés vivants.", 403)
    actor = unpack(party["characters"][player])
    if ids:
        ready(party, player, now, error, redirect=action == "unit_order" and params.get("order") == "move")
    characters = {key: unpack(data) for key, data in party["characters"].items()}
    if action == "control_units":
        charge_control(party, characters, now, [])
        energy = {type(e).__name__: e.current_value for e in characters[player].energie}
        if any(u["control_cost"]["per_second"] and energy.get(u["control_cost"]["energy"], 0) <= 0 and party.get("control_credit", {}).get(player, {}).get(u["control_cost"]["energy"], 0) <= 0 for u in units):
            raise error("control_energy", "Énergie insuffisante pour prendre le contrôle.", 409)
        for key, unit in battle["summons"].items():
            if unit["owner"] != player:
                continue
            if key in ids:
                if not unit.get("controlled"):
                    unit.update(controlled=True, order={"type": "hold"}, route=[], control_at=now)
            else:
                release_control(unit)
        party["characters"] = {key: pack(c) for key, c in characters.items()}
        return ["Contrôle des alliés mis à jour."]
    if not ids or any(not u.get("controlled") for u in units):
        raise error("not_controlled", "Prenez le contrôle des alliés avant de leur donner un ordre.", 409)
    if action == "unit_skill":
        if len(units) != 1:
            raise error("invalid_units", "Une compétence exige une seule invocation contrôlée.")
        unit = units[0]
        invocation = characters[player].invocations.get_all()[unit["index"]]
        skill = invocation.skills.get(params["skill_name"]) if isinstance(params["skill_name"], str) else None
        enemy = next((mob for mob in party["mobs"] if mob["combat_id"] == params["target"]), None)
        if not skill or skill.skill_type.name != "DAMAGE":
            raise error("unknown_skill", "Compétence offensive non acquise.")
        if unit.get("casting") or invocation.is_stunned() or unit.get("skill_ready", {}).get(skill.name, 0) > now or not skill.can_afford(invocation):
            raise error("skill_unavailable", "Énergie, incantation ou délai insuffisant.", 409)
        if not enemy or not visible(party, player, enemy) or distance(unit["position"], enemy["position"]) > progression.attack_range(invocation, skill) or not sight(PRESETS[battle["preset"]], unit["position"], enemy["position"]):
            raise error("out_of_range", "Cible invisible, masquée ou hors de portée.", 409)
        charge_control(party, characters, now, [])
        if not unit.get("controlled"):
            raise error("control_energy", "Le contrôle a expiré.", 409)
        timing = progression.casting(skill)
        invocation.consume_energie(skill.energie_cost, skill.energie_target)
        unit.update(route=[], order={"type": "hold"}, casting={"skill_name": skill.name, "target": enemy["combat_id"], "ends_at": now + timing["seconds"] * progression.RATIO, "concentration": timing["concentration"]})
        unit.setdefault("skill_ready", {})[skill.name] = unit["casting"]["ends_at"] + skill.cooldown * progression.RATIO
        party["characters"] = {key: pack(c) for key, c in characters.items()}
        party["ready"][player] = now + progression.ACTION_SECONDS * progression.RATIO
        return [f"{invocation.name} commence {skill.name}."]
    if any(unit.get("casting") for unit in units):
        raise error("casting", "L’invocation est immobilisée pendant son incantation.", 409)
    order, target, routes = params["order"], params["target"], params["paths"]
    if not isinstance(order, str) or order not in ("move", "attack", "hold") or not isinstance(routes, dict):
        raise error("invalid_order", "Ordre invalide.")
    if order == "move":
        preset = PRESETS[battle["preset"]]
        if not walkable(preset, target) or set(routes) != set(ids):
            raise error("invalid_path", "Destination ou chemins invalides.")
        for key, unit in zip(ids, units):
            route = routes[key]
            if isinstance(route, list) and len(route) <= preset["width"] * preset["height"] and params.get("encounter") is not None and unit["position"] in route and all(walkable(preset, point) for point in route):
                route = route[route.index(unit["position"]) + 1:]
                routes = {**routes, key: route}
            if not isinstance(route, list) or len(route) > preset["width"] * preset["height"] or (route[-1] if route else unit["position"]) != target:
                raise error("invalid_path", "Chemin d’allié invalide.")
            previous = unit["position"]
            for point in route:
                if not walkable(preset, point) or abs(previous[0] - point[0]) + abs(previous[1] - point[1]) != 1:
                    raise error("invalid_path", "Chemin d’allié bloqué ou vitesse impossible.")
                previous = point
    elif order == "attack":
        enemy = next((m for m in party["mobs"] if m["combat_id"] == target), None) if isinstance(target, str) else None
        if not enemy or not visible(party, player, enemy):
            raise error("invisible_target", "Cet ennemi n’est pas visible pour votre groupe.", 409)
        if routes:
            raise error("invalid_order", "L’attaque ne reçoit pas de chemins du client.")
    elif target is not None or routes:
        raise error("invalid_order", "L’attente ne reçoit pas de cible ni de chemins.")
    charge_control(party, characters, now, [])
    if any(not unit.get("controlled") for unit in units):
        raise error("control_energy", "Le contrôle a expiré faute d’énergie.", 409)
    party["characters"] = {key: pack(c) for key, c in characters.items()}
    for key, unit in zip(ids, units):
        unit["order"] = {"type": order, "target": deepcopy(target)}
        unit["route"] = deepcopy(routes.get(key, []))
        unit["next_move"] = max(unit["next_move"], now)
    if order != "move":
        party["ready"][player] = now + progression.ACTION_SECONDS * progression.RATIO
    return [f"Ordre {order} transmis à {len(ids)} allié(s)."]


def visible(party, player, mob):
    battle = party.get("battle")
    if not battle or player not in battle["players"]:
        return False
    observers = [unit for key, unit in battle["players"].items() if party["characters"][key]["stats"]["hp"]["current"] > 0]
    observers.extend(unit for unit in battle.get("summons", {}).values() if unit["hp"] > 0 and party["characters"][unit["owner"]]["stats"]["hp"]["current"] > 0)
    return any(distance(unit["position"], mob["position"]) <= 6 and sight(PRESETS[battle["preset"]], unit["position"], mob["position"]) for unit in observers)


def unalerted_allies(party, mob):
    return [ally for ally in party["mobs"] if ally is not mob and ally["combat_id"] in mob["allies"] and not ally.get("alerted", False) and distance(ally["position"], mob["position"]) < 10]


def view(party, now, player=None):
    battle = party.get("battle")
    if not battle:
        return None
    preset = PRESETS[battle["preset"]]
    result = {**deepcopy(battle), "map": deepcopy(preset), "hostiles_alive": len(party["mobs"])}
    result["intents"] = [{"id": mob["combat_id"], "name": mob["name"], "action": mob["intent"],
                           "remaining_seconds": max(0, (mob.get("calling_until") or mob.get("windup_until") or mob.get("next_attack", now)) - now) / progression.RATIO}
                          for mob in party["mobs"] if player is None or visible(party, player, mob)]
    return result


def allowed(party, player, target, attack_range):
    battle = party.get("battle")
    if not battle or player not in battle["players"]:
        return False
    unit = battle["players"][player]
    enemy = next((m for m in party["mobs"] if m["combat_id"] == target), None)
    other = enemy or battle["players"].get(target)
    return bool(other and (enemy is None or visible(party, player, enemy)) and distance(unit["position"], other["position"]) <= attack_range and sight(PRESETS[battle["preset"]], unit["position"], other["position"]))


def ready(party, player, now, error, redirect=False):
    from .tutorial import unpack
    actor = unpack(party["characters"][player])
    if not actor.is_alive() or actor.is_stunned():
        raise error("stunned" if actor.is_stunned() else "defeated", "Votre personnage ne peut pas agir.", 409)
    if party["ready"][player] > now and not redirect:
        raise error("cooldown", "Attendez la fin du délai de 1,2 seconde.", 409)
    if party.get("battle") and party["battle"]["players"][player].get("casting"):
        raise error("casting", "Votre incantation vous immobilise jusqu’à sa fin.", 409)
    return actor


def execute(party, player, action, params, now, error):
    battle = party.get("battle")
    if not battle:
        raise error("not_fighting", "Aucun champ de bataille actif.", 409)
    actor = ready(party, player, now, error, redirect=action == "battle_move")
    unit = battle["players"][player]
    preset = PRESETS[battle["preset"]]
    if action == "battle_move":
        destination = [params["x"], params["y"]]
        route = params["path"]
        if not walkable(preset, destination) or not isinstance(route, list) or len(route) > preset["width"] * preset["height"] or not route or route[-1] != destination:
            raise error("invalid_path", "Trajet invalide.")
        if params.get("encounter") is not None and unit["position"] in route and all(walkable(preset, point) for point in route):
            route = route[route.index(unit["position"]) + 1:]
        previous = unit["position"]
        for point in route:
            if not walkable(preset, point) or abs(point[0] - previous[0]) + abs(point[1] - previous[1]) != 1:
                raise error("invalid_path", "Trajet bloqué ou vitesse impossible.")
            previous = point
        moving = bool(unit["route"])
        unit["route"] = deepcopy(route)
        if not moving:
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
    if action != "battle_move":
        party["ready"][player] = now + progression.ACTION_SECONDS * progression.RATIO
    return messages


def damaged(party, mob, actor, now):
    battle = party["battle"]
    unit = battle["players"].get(actor) or battle.get("summons", {}).get(actor)
    unit["hidden"] = False
    unit["route"] = []
    was_calling = mob["calling_until"] is not None
    mob["calling_until"] = None
    mob["next_call"] = now + CALL_TIME if was_calling else mob["next_call"]
    mob["alerted"] = True
    mob["needs_call"] = True
    if sees(PRESETS[battle["preset"]], mob, unit):
        mob["target"] = actor
        mob["last_known"] = unit["position"][:]
        mob["state"] = "chase"
    else:
        mob["target"] = None
        mob["last_known"] = unit["position"][:]
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
    sync_summons(party, now)
    characters = {key: unpack(data) for key, data in party["characters"].items()}
    for key, unit in battle["players"].items():
        actor = characters[key]
        if unit["route"] and actor.is_alive() and not actor.is_stunned() and unit["next_move"] <= now:
            unit["position"] = unit["route"].pop(0)
            unit["next_move"] = now + MOVE_TIME
    charge_control(party, characters, now, messages)
    advance_summons(party, characters, now, random, messages)
    units = {**battle["players"], **battle.get("summons", {})}
    for key, unit in battle.get("summons", {}).items():
        invocations = characters[unit["owner"]].invocations.get_all()
        if unit["index"] < len(invocations):
            characters[key] = invocations[unit["index"]]
    for mob in party["mobs"]:
        if any(characters[key].is_alive() and sees(preset, mob, unit) for key, unit in units.items()):
            mob["alerted"] = True
    for mob in party["mobs"]:
        if not walkable(preset, mob["position"]):
            mob["position"] = free_position(preset, mob["position"])
        if mob.get("stunned_until", 0) > now:
            mob["calling_until"] = None
            mob["windup_until"] = None
            mob["intent"] = "Étourdi : aucune action"
            continue
        if mob.get("stunned_until"):
            mob["stunned_until"] = 0
            mob["effects"] = [e for e in mob["effects"] if e["group"] != "stun"]
            if not any(c.is_alive() and sees(preset, mob, units[key]) for key, c in characters.items()):
                mob.update(state="patrol", target=None, last_known=None, search_until=None, needs_call=False)
        for corpse in battle["corpses"]:
            if distance(mob["position"], corpse["position"]) <= 5 and sight(preset, mob["position"], corpse["position"]) and corpse["id"] not in mob["known_dead"]:
                mob["known_dead"].append(corpse["id"])
        visible = [(distance(mob["position"], unit["position"]), key) for key, unit in units.items()
                   if characters[key].is_alive() and sees(preset, mob, unit) and path(preset, mob["position"], unit["position"]) is not None]
        visible.sort()
        target = visible[0][1] if visible else None
        if target:
            mob["alerted"] = True
            previous = mob.get("target")
            mob["target"] = target
            mob["last_known"] = units[target]["position"][:]
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
        if mob["calling_until"] is not None and not unalerted_allies(party, mob):
            mob["calling_until"] = None
        if mob["calling_until"] is not None:
            mob["intent"] = "Appel aux alliés"
            if mob["calling_until"] <= now:
                mob["calling_until"] = None
                mob["next_call"] = now + CALL_TIME
                messages.append(f"{mob['name']} appelle ses alliés.")
                for ally in unalerted_allies(party, mob):
                    ally["alerted"] = True
                    ally["last_known"] = deepcopy(mob["last_known"])
                    ally["state"] = "search"
                    ally["search_until"] = now + SEARCH_TIME
            continue
        if mob.get("needs_call") and mob["next_call"] <= now and unalerted_allies(party, mob):
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
                before_hp = actor.hp.current_value
                actor.lose_hp(enemy, 3)
                cast = units[target].get("casting")
                if cast and cast["concentration"] and actor.hp.current_value < before_hp:
                    units[target].pop("casting", None)
                    messages.append(f"{actor.name} : concentration brisée, sort annulé.")
                mob["windup_until"] = None
                mob["next_attack"] = now + 9 + random() * 6
                messages.append(f"{mob['name']} utilise Entaille contre {actor.name}.")
            elif mob["windup_until"] is None and mob["next_attack"] <= now:
                mob["windup_until"] = now + 1.8
            mob["intent"] = "Va utiliser Entaille" if mob["windup_until"] else "Prépare sa prochaine attaque"
        else:
            mob["windup_until"] = None
            destination = mob["last_known"] if mob["state"] == "search" else units[target]["position"] if target else None
            if mob["state"] == "search" and mob.get("search_until", now) <= now:
                mob.update(state="patrol", last_known=None, search_until=None)
                destination = None
            if mob["state"] == "search" and destination and distance(mob["position"], destination) < 1:
                candidates = [[destination[0] + dx, destination[1] + dy] for dx, dy in ((2, 0), (0, 2), (-2, 0), (0, -2))]
                candidates = [p for p in candidates if walkable(preset, p)]
                if candidates:
                    destination = candidates[int(now / 6) % len(candidates)]
            if destination is None:
                patrol = mob.setdefault("patrol_route", patrol_route(preset, 0))
                index = mob.setdefault("patrol_index", 0)
                if mob["position"] == patrol[index]:
                    index = (index + 1) % len(patrol)
                    mob["patrol_index"] = index
                destination = patrol[index]
            route = path(preset, mob["position"], destination)
            if route and mob["next_move"] <= now:
                mob["position"] = route[0]
                mob["next_move"] = now + GOBLIN_MOVE_TIME
            mob["intent"] = "Poursuit un joueur" if target else "Cherche à la dernière position connue" if mob["state"] == "search" else "Patrouille"
    party["characters"] = {key: pack(characters[key]) for key in party["characters"]}
    sync_summons(party, now)
    if not any(characters[key].is_alive() for key in party["characters"]):
        party.update(mobs=[], mob=None, battle=None, journey=[], transit=None, position="rosee" if "rosee" in party["visited"] else "clearing")
        if party["step"] == "first_fight":
            party["step"] = "clearing"
        for key in party["characters"]:
            character = characters[key]
            recover(character)
            party["characters"][key] = pack(character)
        messages.append("Le groupe est secouru et quitte le champ de bataille.")
    return messages
