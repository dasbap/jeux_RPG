from copy import deepcopy
import uuid

from . import tactics, world, progression, content
from .map_building import spawners, create_mob, map_level, zone_of


def terrain(identifier, name, width, height, cover, exits, mobs=(), sites=()):
    return {"id": "field_" + identifier, "name": name, "width": width, "height": height, "cell_metres": 2,
            "cover": [list(point) for point in cover], "exits": exits, "spawns": [list(point) for point in mobs], "sites": list(sites)}


def gate(x, y, destination, entry, name):
    return {"position": [x, y], "destination": destination, "entry": entry, "name": name}


def arrival_point(identifier, source=None):
    definition = MAPS[identifier]
    origin = world.zone_of(source)
    if source in world.ROAD_POINTS:
        route = next(route for route in world.ROUTES if route["id"] == source)
        origin = route["to"] if route["from"] == world.zone_of(identifier) else route["from"]
    passage = next((item for item in definition["exits"] if item["destination"] == origin or item.get("fast_destination") == origin), definition["exits"][0])
    x, y = passage["position"]
    return [1 if x == 0 else definition["width"] - 2 if x == definition["width"] - 1 else x,
            1 if y == 0 else definition["height"] - 2 if y == definition["height"] - 1 else y]


from .map_assets import configured, read_catalog

MAPS = configured(read_catalog("fields"))
tactics.PRESETS.update({definition["id"]: definition for definition in MAPS.values()})
for place in world.PLACES.values():
    place["points"] = [point for point in place["points"] if point["id"] not in {"cave_2", "cave_3"} - MAPS.keys()]

for identifier in MAPS:
    root_zone = zone_of(MAPS, identifier)
    if root_zone not in world.PLACES:
        world.PLACES[root_zone] = {"name": MAPS[root_zone]["name"], "type": "zone", "x": 70, "y": 300 + 30 * len(world.PLACES), "description": "Zone personnalisée.", "points": []}
        world.LEVELS[root_zone] = MAPS[root_zone].get("zone_level", 1)
for identifier, definition in MAPS.items():
    zone = world.zone_of(identifier)
    parent_zone = zone_of(MAPS, identifier)
    if parent_zone == identifier:
        parent_zone = definition.get("world_zone")
    if identifier not in world.PLACES and parent_zone in world.PLACES and zone != parent_zone:
        for place in world.PLACES.values():
            place["points"] = [point for point in place["points"] if point["id"] != identifier]
        zone = None
    if zone is None and parent_zone in world.PLACES:
        world.PLACES[parent_zone]["points"].append({"id": identifier, "name": definition["name"], "type": "rencontre", "description": "Secteur de forêt à explorer à pied."})
        zone = parent_zone
    if identifier in world.PLACES:
        world.PLACES[identifier]["name"] = definition["name"]
    elif zone:
        for point in world.PLACES[zone]["points"]:
            if point["id"] == identifier:
                point["name"] = definition["name"]
    if zone is None:
        world.PLACES[identifier] = {"name": definition["name"], "type": "zone", "x": 70, "y": 300 + 30 * len(world.PLACES), "description": "Zone personnalisée.", "points": []}
        world.LEVELS[identifier] = 1

for identifier in MAPS:
    root_zone = zone_of(MAPS, identifier)
    if root_zone in world.LEVELS:
        world.LEVELS[root_zone] = MAPS[root_zone].get("zone_level", world.LEVELS[root_zone])


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
    companions = deepcopy(party.get("battle", {}).get("companions", {})) if party.get("battle") else deepcopy(party.get("linked_companions", {}))
    party["position"] = identifier
    party["field_map"] = identifier
    if identifier == "rosee" and party["step"] == "road":
        party["step"] = "village"
    party["visited"] = sorted(set(party.get("visited", [])) | {world.zone_of(identifier)})
    from . import achievements
    achievements.record(party)
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
        configurations = spawners(definition)
        for index, config in enumerate(configurations):
            mob = create_mob(MAPS, identifier, config, index, first)
            party["mobs"].append({**mob, "combat_id": f"{identifier}-mob-{index}", "next_attack": now + 6})
        tactics.begin(party, now, "explore")
        occupied = []
        for mob, config in zip(party["mobs"], configurations):
            position = tactics.free_position(definition, config["position"], occupied)
            occupied.append(position)
            mob.update(position=position, home=position[:], patrol_route=deepcopy(config.get("patrol")) or [tactics.free_position(definition, [position[0] + dx, position[1] + dy]) for dx, dy in ((0, 0), (4, 0), (4, 4), (-3, 4))], patrol_index=0)
    if saved and now - saved["saved_at"] >= content.WORLD["repop_seconds"]:
        progression.health_resources(party, now)
        repop(party, identifier, now, pursuers)
    occupied = []
    party["battle"]["players"] = {}
    for key in party["characters"]:
        position = tactics.free_position(definition, entry, occupied)
        occupied.append(position)
        party["battle"]["players"][key] = {"position": position, "hidden": False, "route": [], "next_move": now, "detected": False}
    party["battle"]["companions"] = companions
    for unit in companions.values():
        owner = party["battle"]["players"].get(unit["owner"])
        if owner:
            unit.update(position=tactics.free_position(definition, owner["position"], occupied), next_move=now)
            occupied.append(unit["position"])
    party["linked_companions"] = deepcopy(companions)
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
        party["seen_mobs"] = sorted(set(party.get("seen_mobs", [])) | {mob.get("mob_id", "goblin") for mob in party["mobs"]})
        party["seen_spawnpoints"] = sorted(set(party.get("seen_spawnpoints", [])) | {identifier})
    reveal(party)
    return [f"Vous entrez dans {definition['name']}."]


def transition(party, gate, player, now):
    from . import tutorial
    battle = party["battle"]
    definition = MAPS[party["field_map"]]
    unit = battle["players"][player]
    pursuers = [mob for mob in party["mobs"] if mob.get("alerted") and not mob.get("stunned_until", 0) > now and tactics.sees(definition, mob, unit) and tactics.path(definition, mob["position"], unit["position"]) is not None] if gate["destination"] and not gate.get("travel_minutes", 0) else []
    remaining = [mob for mob in party["mobs"] if mob not in pursuers]
    party["fields"][party["field_map"]] = snapshot(party, now, remaining)
    if gate["destination"] and gate.get("travel_minutes", 0) > 0:
        duration = gate["travel_minutes"] * 60
        party["linked_companions"] = deepcopy(battle.get("companions", {}))
        party.update(battle=None, mobs=[], mob=None, journey=[])
        party.pop("field_map", None)
        party["transit"] = {"source": party["position"], "destination": gate["destination"], "field_entry": gate["entry"][:], "remaining": duration, "total": duration, "segment": duration, "started_at": now, "ready_at": now + duration, "hazard": False}
        return [f"Vous empruntez {gate['name']} ({gate['travel_minutes']:g} min en jeu)."]
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
    party["field_return_from"] = party["field_map"]
    x, y = gate["position"]
    party["field_return_entry"] = [1 if x == 0 else definition["width"] - 2 if x == definition["width"] - 1 else x, 1 if y == 0 else definition["height"] - 2 if y == definition["height"] - 1 else y]
    party["linked_companions"] = deepcopy(battle.get("companions", {}))
    party.update(battle=None, mobs=[], mob=None)
    party.pop("field_map", None)
    party["position"] = definition.get("fast_travel_origin", party["position"])
    if party["position"] == "clearing" and party["step"] in ("clearing", "first_fight"):
        party["step"] = "road"
    return ["Vous quittez complètement la zone et rejoignez les chemins rapides. Les ennemis cessent la poursuite."]


def interactions(party, player):
    if not party.get("field_map") or not party.get("battle"):
        return []
    definition = MAPS[party["field_map"]]
    unit = party["battle"]["players"][player]
    sites = [site for site in definition["sites"] if not site.get("owner")] + list(party["battle"].get("companions", {}).values())
    return [site for site in sites if tactics.distance(unit["position"], site["position"]) <= 1.5]


def execute(party, player, action, params, now, error, random):
    from . import tutorial, forge
    nearby = interactions(party, player)
    site = params.get("npc") if action == "talk" else "forge"
    if site not in {item["id"] for item in nearby}:
        raise error("wrong_location", "Approchez-vous du lieu pour interagir.", 409)
    unit = party["battle"]["players"][player]
    if any(tactics.sees(MAPS[party["field_map"]], mob, unit) for mob in party["mobs"]):
        raise error("in_combat", "Les ennemis vous menacent : impossible d’interagir.", 409)
    if action == "talk" and site != "mira":
        npc = next(item for item in nearby if item["id"] == site)
        return [f"{npc['name']} : {npc.get('dialogue') or 'Bonjour, voyageur.'}", *content.quest_dialogue(party, site)], False
    if action == 'talk' and site == 'mira' and (party['step'] not in ('village', 'hunt') or party['step'] == 'hunt' and party['kills'] < content.HUNT['count'] and any(q['npc'] == 'mira' and not content.is_hunt(q) for q in content.DATA['quests'])):
        npc = next(item for item in nearby if item['id'] == site)
        return [f"{npc['name']} : {npc.get('dialogue') or 'Bonjour !'}", *content.quest_dialogue(party, site)], False
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
    observers = [(unit, tactics.PLAYER_VISION) for key, unit in battle["players"].items() if party["characters"][key]["stats"]["hp"]["current"] > 0]
    observers.extend((unit, tactics.SUMMON_VISION) for unit in battle.get("summons", {}).values() if unit["hp"] > 0 and party["characters"][unit["owner"]]["stats"]["hp"]["current"] > 0)
    positions = [[unit["position"], radius] for unit, radius in observers]
    if positions == battle.get("explored_positions"):
        return
    definition = MAPS[party["field_map"]]
    explored = {tuple(point) for point in battle.get("explored", [])}
    for (x, y), radius in positions:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius and 0 <= x + dx < definition["width"] and 0 <= y + dy < definition["height"]:
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


def repop(party, identifier, now, pursuers=()):
    from . import tutorial
    from jeuxRPG._class.character import Character
    definition = MAPS[identifier]
    existing = list(party["mobs"]) + list(pursuers)
    existing.extend(arrival["mob"] for arrival in party["battle"].get("arrivals", []))
    for saved in party.get("fields", {}).values():
        existing.extend(saved["mobs"])
        existing.extend(arrival["mob"] for arrival in saved["battle"].get("arrivals", []))
    origins = {mob["combat_id"].split(":repop:")[0] for mob in existing}
    count = 0
    for index, config in enumerate(spawners(definition)):
        position = config["position"]
        origin = f"{identifier}-mob-{index}"
        if origin in origins:
            continue
        mob = create_mob(MAPS, identifier, config, index, identifier == "clearing")
        party["mobs"].append({**mob, "combat_id": origin + ":repop:" + uuid.uuid4().hex, "next_attack": now + 6,
            "position": tactics.free_position(definition, position, [mob["position"] for mob in party["mobs"]]), "home": position[:], "state": "patrol", "target": None, "last_known": None, "search_until": None,
            "next_move": now + tactics.GOBLIN_MOVE_TIME, "next_call": now, "calling_until": None, "windup_until": None,
            "known_dead": [], "allies": [], "intent": "Patrouille", "stunned_until": 0,
            "patrol_route": deepcopy(config.get("patrol")) or [tactics.free_position(definition, [position[0] + dx, position[1] + dy]) for dx, dy in ((0, 0), (4, 0), (4, 4), (-3, 4))], "patrol_index": 0})
        count += 1
    if count:
        party["battle"].update(initial_mobs=len(party["mobs"]), awarded=False, started_at=now, combat_step=party["step"], defeated_targets=[], enemy_alerted=False, damage_received=False,
                              higher_level=any(mob["level"] > max(c["level"] for c in party["characters"].values()) for mob in party["mobs"]))


def migrate_terrain(party):
    battle = party.get("battle")
    if not battle:
        return
    if battle["preset"] not in tactics.PRESETS:
        destination = "cave_1" if party.get("field_map", "").startswith("cave_") else world.CURRENT[party["step"]]
        party["linked_companions"] = deepcopy(battle.get("companions", {}))
        party.update(position=destination, battle=None, mobs=[], mob=None, transit=None, journey=[])
        party.pop("field_map", None)
        party.pop("field_return_from", None)
        party.pop("field_return_entry", None)
        return
    definition = tactics.PRESETS[battle["preset"]]
    version = definition.get("terrain_version", 1)
    if battle.get("terrain_version") == version:
        return
    occupied = []
    for unit in [*battle["players"].values(), *battle.get("summons", {}).values(), *battle.get("companions", {}).values(), *party["mobs"]]:
        unit["position"] = tactics.free_position(definition, unit["position"], occupied)
        occupied.append(unit["position"])
        if "route" in unit:
            unit["route"] = []
        if "home" in unit:
            unit["home"] = tactics.free_position(definition, unit["home"])
        if "patrol_route" in unit:
            unit["patrol_route"] = [tactics.free_position(definition, point) for point in unit["patrol_route"]]
    battle["terrain_version"] = version
