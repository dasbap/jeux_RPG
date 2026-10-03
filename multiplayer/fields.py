from copy import deepcopy

from . import tactics, world, progression


def terrain(identifier, name, width, height, cover, exits, mobs=(), sites=()):
    return {"id": "field_" + identifier, "name": name, "width": width, "height": height, "cell_metres": 2,
            "cover": [list(point) for point in cover], "exits": exits, "spawns": [list(point) for point in mobs], "sites": sites}


def gate(x, y, destination, entry, name):
    return {"position": [x, y], "destination": destination, "entry": entry, "name": name}


MAPS = {
    "clearing": terrain("clearing", "Forêt des Éveillés", 30, 20,
        [(x, y) for x in (5, 10, 20, 24) for y in (2, 3, 6, 7, 14, 15)],
        [gate(29, 10, None, None, "Chemin rapide vers Rosée")], [(17, 10)]),
    "rosee": terrain("rosee", "Village de Rosée", 64, 40,
        [(x, y) for left, top in ((15, 5), (28, 5), (41, 5), (15, 27), (28, 27), (41, 27)) for x in range(left, left + 6) for y in range(top, top + 6)],
        [gate(0, 20, None, None, "Chemin rapide"), gate(63, 20, "lisiere", [1, 10], "Lisière"), gate(32, 0, "cave_1", [1, 7], "Grotte"), gate(32, 39, "forest", [1, 12], "Forêt")],
        sites=[{"id": "mira", "name": "Place · Mira", "position": [32, 20]}, {"id": "forge", "name": "Forge · rue des artisans", "position": [44, 12]}]),
    "lisiere": terrain("lisiere", "Entrée de la lisière", 30, 20,
        [(x, y) for x in (7, 14, 23) for y in (3, 4, 14, 15)],
        [gate(0, 10, "rosee", [62, 20], "Village de Rosée"), gate(29, 10, "hunt", [1, 10], "Campement gobelin"), gate(15, 0, "cave_1", [11, 1], "Grotte"), gate(15, 19, "forest", [20, 1], "Forêt")]),
    "hunt": terrain("hunt", "Campement gobelin", 30, 20,
        [(12, 5), (12, 6), (18, 13), (19, 13), (22, 4)],
        [gate(0, 10, "lisiere", [28, 10], "Entrée de la lisière"), gate(29, 10, "forest", [20, 24], "Forêt")], [(17, 8), (21, 11), (24, 7)]),
    "forest": terrain("forest", "Forêt de Rosée", 40, 26,
        [(x, y) for x in (8, 15, 24, 31) for y in (3, 4, 8, 9, 18, 19)],
        [gate(0, 12, "rosee", [32, 38], "Village de Rosée"), gate(20, 0, "lisiere", [15, 18], "Lisière"), gate(20, 25, "hunt", [28, 10], "Campement gobelin"), gate(39, 12, None, None, "Sortie complète · chemins rapides")], [(18, 12), (28, 16)]),
    "cave_1": terrain("cave_1", "Grotte · salle 1", 22, 16,
        [(8, 3), (8, 4), (13, 11), (14, 11)],
        [gate(0, 7, "rosee", [32, 1], "Village de Rosée"), gate(21, 7, "cave_2", [1, 7], "Salle 2"), gate(11, 0, "lisiere", [15, 1], "Lisière")], [(13, 7)]),
    "cave_2": terrain("cave_2", "Grotte · salle 2", 22, 16,
        [(7, 3), (7, 4), (14, 11), (14, 12)],
        [gate(0, 7, "cave_1", [20, 7], "Salle 1"), gate(21, 7, "cave_3", [1, 7], "Salle 3")], [(12, 7), (16, 9)]),
    "cave_3": terrain("cave_3", "Grotte · salle 3 · impasse", 22, 16,
        [(7, 3), (7, 4), (14, 11), (14, 12)],
        [gate(0, 7, "cave_2", [20, 7], "Salle 2")], [(14, 7)]),
    "brume": terrain("brume", "Village de Brume", 48, 32,
        [(x, y) for left, top in ((12, 5), (25, 5), (12, 23), (25, 23)) for x in range(left, left + 5) for y in range(top, top + 5)],
        [gate(0, 16, None, None, "Chemins rapides")]),
}

tactics.PRESETS.update({definition["id"]: definition for definition in MAPS.values()})


def start(party, now):
    from . import tutorial
    tutorial.migrate(party, now)
    party["field_mode"] = True
    party["fields"] = {}
    return enter(party, "clearing", [1, 10], now)


def enter(party, identifier, entry, now, pursuers=()):
    from . import tutorial
    from jeuxRPG._class.character import Character
    definition = MAPS[identifier]
    party["position"] = identifier
    party["field_map"] = identifier
    if identifier == "rosee" and party["step"] == "road":
        party["step"] = "village"
    party["visited"] = sorted(set(party.get("visited", [])) | {world.zone_of(identifier)})
    saved = party.setdefault("fields", {}).pop(identifier, None)
    party["encounter_number"] = party.get("encounter_number", 0) + 1
    party["training"] = False
    if saved:
        party["mobs"] = saved["mobs"]
        party["battle"] = saved["battle"]
        party.setdefault("hp_regen", {}).update(saved.get("hp_regen", {}))
        for mob in party["mobs"]:
            mob.update(target=None, state="patrol", last_known=None, calling_until=None, windup_until=None, next_move=now + tactics.GOBLIN_MOVE_TIME)
        party["battle"].update(next_brain=now, summons={})
    else:
        party["mobs"] = []
        first = identifier == "clearing" and party["step"] == "clearing"
        party["combat_step"] = "first_fight" if first else party["step"]
        if first:
            party["step"] = "first_fight"
        for index, position in enumerate(definition["spawns"]):
            actor = Character.create("Goblin", "tutorial-mob", f"Gobelin des bois {index + 1}")
            actor.hp.value = world.GOBLIN["hp_first"] if first else world.GOBLIN["hp_hunt"]
            actor.hp.current_value = actor.hp.value
            party["mobs"].append({**tutorial.pack(actor), "combat_id": f"{identifier}-mob-{index}", "rank": "D", "next_attack": now + 6})
        tactics.begin(party, now, "explore")
        for mob, position in zip(party["mobs"], definition["spawns"]):
            mob.update(position=position[:], home=position[:], patrol_route=[tactics.free_position(definition, [position[0] + dx, position[1] + dy]) for dx, dy in ((0, 0), (4, 0), (4, 4), (-3, 4))], patrol_index=0)
    occupied = []
    party["battle"]["players"] = {}
    for key in party["characters"]:
        position = tactics.free_position(definition, entry, occupied)
        occupied.append(position)
        party["battle"]["players"][key] = {"position": position, "hidden": False, "route": [], "next_move": now, "detected": False}
    party["battle"]["combat_step"] = party["combat_step"]
    party["battle"].setdefault("arrivals", [])
    for enemy in pursuers:
        enemy = deepcopy(enemy)
        enemy.update(position=tactics.free_position(definition, entry, occupied), home=entry[:], target=None, state="search", last_known=entry[:], search_until=now + tactics.SEARCH_TIME,
                     next_move=now + tactics.GOBLIN_MOVE_TIME, calling_until=None, windup_until=None, next_call=now + tactics.CALL_TIME, alerted=True,
                     patrol_route=tactics.patrol_route(definition, 0), patrol_index=0)
        occupied.append(enemy["position"])
        party["battle"]["arrivals"].append({"mob": enemy, "arrive_at": enemy.pop("arrive_at", now), "entry": entry[:]})
    if pursuers:
        party["battle"].update(initial_mobs=party["battle"].get("initial_mobs", 0) + len(pursuers), awarded=False, started_at=now)
    identifiers = [mob["combat_id"] for mob in party["mobs"]]
    for mob in party["mobs"]:
        mob["allies"] = [key for key in identifiers if key != mob["combat_id"]]
    party["combat_step"] = party["battle"].get("combat_step", party["step"])
    tutorial.sync_mobs(party)
    progression.health_resources(party, now)
    if party["mobs"]:
        party["seen_mobs"] = sorted(set(party.get("seen_mobs", [])) | {"goblin"})
        party["seen_spawnpoints"] = sorted(set(party.get("seen_spawnpoints", [])) | {identifier})
    reveal(party)
    return [f"Vous entrez dans {definition['name']}."]


def transition(party, gate, player, now):
    from . import tutorial
    battle = party["battle"]
    definition = MAPS[party["field_map"]]
    unit = battle["players"][player]
    pursuers = [mob for mob in party["mobs"] if mob.get("alerted") and not mob.get("stunned_until", 0) > now and tactics.sees(definition, mob, unit) and tactics.path(definition, mob["position"], unit["position"]) is not None] if gate["destination"] else []
    remaining = [mob for mob in party["mobs"] if mob not in pursuers]
    party["fields"][party["field_map"]] = snapshot(party, now, remaining)
    if gate["destination"]:
        followers = []
        for mob in pursuers:
            follower = deepcopy(mob)
            route = tactics.path(definition, mob["position"], unit["position"])
            previous = mob["position"]
            duration = tactics.GOBLIN_MOVE_TIME
            for point in route:
                duration += tactics.step_time(previous, point, tactics.GOBLIN_MOVE_TIME)
                previous = point
            follower["arrive_at"] = now + duration
            followers.append(follower)
        messages = enter(party, gate["destination"], gate["entry"], now, followers)
        if pursuers:
            messages.append(f"{len(pursuers)} ennemi(s) vous poursuivent dans cette zone.")
        return messages
    party.update(battle=None, mobs=[], mob=None)
    party.pop("field_map", None)
    if party["position"] == "clearing" and party["step"] in ("clearing", "first_fight"):
        party["step"] = "road"
    return ["Vous quittez complètement la zone et rejoignez les chemins rapides. Les ennemis cessent la poursuite."]


def interactions(party, player):
    if not party.get("field_map") or not party.get("battle"):
        return []
    definition = MAPS[party["field_map"]]
    unit = party["battle"]["players"][player]
    return [site for site in definition["sites"] if tactics.distance(unit["position"], site["position"]) <= 1.5]


def execute(party, player, action, params, now, error, random):
    from . import tutorial, forge
    nearby = interactions(party, player)
    site = "mira" if action == "talk" else "forge"
    if action == "talk" and params.get("npc") != "mira":
        raise error("invalid_npc", "Ce PNJ n’est pas présent ici.", 409)
    if site not in {item["id"] for item in nearby}:
        raise error("wrong_location", "Approchez-vous du lieu pour interagir.", 409)
    unit = party["battle"]["players"][player]
    if any(tactics.sees(MAPS[party["field_map"]], mob, unit) for mob in party["mobs"]):
        raise error("in_combat", "Les ennemis vous menacent : impossible d’interagir.", 409)
    battle, position = party["battle"], party["position"]
    party.update(battle=None, position=site)
    try:
        if action in ("craft", "upgrade"):
            return forge.execute(party, player, action, params["recipe"], error)
        return tutorial.execute_one(party, player, action, params, now, error, random)
    finally:
        party.update(battle=battle, position=position)


def reveal(party):
    if not party.get("field_map") or not party.get("battle"):
        return
    battle = party["battle"]
    units = {**battle["players"], **battle.get("summons", {})}
    positions = [unit["position"] for unit in units.values()]
    if positions == battle.get("explored_positions"):
        return
    definition = MAPS[party["field_map"]]
    explored = {tuple(point) for point in battle.get("explored", [])}
    for x, y in positions:
        for dx in range(-6, 7):
            for dy in range(-6, 7):
                if dx * dx + dy * dy <= 36 and 0 <= x + dx < definition["width"] and 0 <= y + dy < definition["height"]:
                    explored.add((x + dx, y + dy))
    battle["explored"] = [list(point) for point in sorted(explored)]
    battle["explored_positions"] = deepcopy(positions)


def advance(party, now):
    if not party.get("field_map") or not party.get("battle"):
        return []
    battle = party["battle"]
    definition = MAPS[party["field_map"]]
    messages = []
    waiting = []
    occupied = [unit["position"] for unit in battle["players"].values()] + [mob["position"] for mob in party["mobs"]]
    for arrival in battle.get("arrivals", []):
        if now < arrival["arrive_at"]:
            waiting.append(arrival)
            continue
        mob = arrival["mob"]
        mob.update(position=tactics.free_position(definition, arrival["entry"], occupied), next_move=now + tactics.GOBLIN_MOVE_TIME, next_attack=now + tactics.GOBLIN_MOVE_TIME, search_until=now + tactics.SEARCH_TIME)
        occupied.append(mob["position"])
        party["mobs"].append(mob)
        messages.append(f"{mob['name']} vous a suivi dans la zone.")
    battle["arrivals"] = waiting
    identifiers = [mob["combat_id"] for mob in party["mobs"]]
    for mob in party["mobs"]:
        mob["allies"] = [key for key in identifiers if key != mob["combat_id"]]
    if messages:
        from . import tutorial
        tutorial.sync_mobs(party)
    return messages


def snapshot(party, now, mobs=None):
    battle = party["battle"]
    prefix = f"mob:{battle['started_at']}:"
    return {"battle": deepcopy(battle), "mobs": deepcopy(party["mobs"] if mobs is None else mobs), "saved_at": now,
            "hp_regen": {key: deepcopy(value) for key, value in party.get("hp_regen", {}).items() if key.startswith(prefix)}}
