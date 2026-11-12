import json
import os
from copy import deepcopy
from pathlib import Path

from jeuxRPG._class.res.character.table_stat_subclass import goblin_table

from . import content
from .forge import RARE_DROPS
from .map_assets import read_catalog
from .world_topology import compile_world

# No runtime world defaults: the selected Builder catalogue owns all geography.
world_source = os.environ.get("RPG_MAPS_FILE")
WORLD_MAP_DATA = (
    json.loads(Path(world_source).read_text(encoding="utf-8"))
    if world_source and Path(world_source).is_file()
    else read_catalog("fields", Path(world_source) if world_source else None)
)
WORLD_MAP_DATA = WORLD_MAP_DATA.get("maps", WORLD_MAP_DATA)
(PLACES, VILLAGE_STREETS, ROUTES, LEVELS, POINT_MAPS, ZONE_ENTRIES, EDGES) = (
    compile_world(WORLD_MAP_DATA)
)

CURRENT = {
    stage: content.gameplay()["rules"]["start"]["map"]
    for stage in content.gameplay()["story"]
}
GOBLIN = {
    **content.DATA["gameplay"]["rules"]["tutorial"],
    "loot": {"peau": 1, "croc": 1},
}


def discovery(party):
    visited = {content.gameplay()["rules"]["start"]["map"], *party.get("visited", [])}
    mobs = set(party.get("seen_mobs", []))
    if party.get("mob"):
        mobs.add("goblin")
    return visited, mobs


def record(party):
    visited, mobs = discovery(party)
    party["visited"] = sorted(visited)
    party["seen_mobs"] = sorted(mobs)


def _known_places(visited, step):
    # Geography is authored, never unlocked by a tutorial stage.
    return set(PLACES)


def _visible_routes(known, step, fighting, moving):
    routes = []
    definitions = list(ROUTES)
    for source, data in WORLD_MAP_DATA.items():
        for index, gate in enumerate(data.get("exits", [])):
            if gate.get("destination") in WORLD_MAP_DATA:
                minutes = gate.get("travel_minutes", 0)
                definitions.append(
                    {
                        "id": f"passage_{source}_{index}",
                        "name": gate["name"],
                        "from": source,
                        "to": gate["destination"],
                        "distance_km": minutes
                        / 60
                        * content.gameplay()["rules"]["movement"]["walking_kmh"],
                        "bidirectional": False,
                        "kind": "trajet" if minutes else "passage",
                        "from_map_name": data["name"],
                        "to_map_name": WORLD_MAP_DATA[gate["destination"]]["name"],
                        "duration_game_seconds": minutes * 60,
                    }
                )
    for definition in definitions:
        if zone_of(definition["from"]) in known and zone_of(definition["to"]) in known:
            route = {**definition, "destination": None}
            route["duration_game_seconds"] = definition.get(
                "duration_game_seconds",
                definition["distance_km"]
                / content.gameplay()["rules"]["movement"]["walking_kmh"]
                * 3600,
            )
            route["duration_real_seconds"] = (
                route["duration_game_seconds"]
                / content.gameplay()["rules"]["time"]["game_ratio"]
            )
            if not fighting and not moving:
                route["destination"] = definition["to"]
            for endpoint in ("from", "to"):
                map_id = route[endpoint]
                if map_id in WORLD_MAP_DATA:
                    parent = WORLD_MAP_DATA[map_id].get("zone_id")
                    if parent in PLACES:
                        route[endpoint] = parent
            if route["from"] != route["to"]:
                routes.append(route)
    return routes


def view(party, me, traveller=None):
    visited, mobs = discovery(party)
    visited = {zone_of(point) for point in visited} - {None}
    step = party["step"]
    known = _known_places(visited, step)
    fighting = bool(party.get("battle") or party["mob"] or party.get("mobs"))
    moving = bool(party.get("transit") or party.get("journey"))
    places = []
    for key, definition in PLACES.items():
        if key not in known:
            continue
        if (
            key in WORLD_MAP_DATA
            and WORLD_MAP_DATA[key].get("zone_id") in PLACES
            and WORLD_MAP_DATA[key]["zone_id"] != key
        ):
            continue
        place = {
            "id": key,
            "name": definition["name"],
            "type": definition["type"],
            "x": definition["x"],
            "y": definition["y"],
            "visited": key in visited,
            "level": LEVELS.get(key, 1),
            "description": definition["description"]
            if key in visited
            else "Lieu connu, encore non visité. Ses détails seront révélés à votre arrivée.",
            "points": deepcopy(definition["points"]) if key in visited else [],
            "entry": deepcopy(definition.get("entry", [70, 110])),
        }
        if (
            traveller
            and key in visited
            and key in ("rosee", "brume")
            and traveller["location"]
            and traveller["location"] in definition["name"]
        ):
            place["points"].append(
                {
                    "id": "leon",
                    "name": traveller["name"],
                    "type": "pnj",
                    "x": 170,
                    "y": 175,
                    "description": "Marchand itinérant actuellement présent sur la place du village. Son passage suit l'horloge du monde.",
                }
            )
        for point in place["points"]:
            point["action"] = None
            point["locked_reason"] = None
            current_zone = zone_of(party.get("position", CURRENT[step]))
            if current_zone in WORLD_MAP_DATA:
                current_zone = WORLD_MAP_DATA[current_zone].get("zone_id", current_zone)
            point["local"] = (
                key == current_zone and party.get("position") not in ROAD_POINTS
            )
            point["can_interact"] = point["local"] and not fighting and not moving
            if (
                not fighting
                and not moving
                and party.get("position", CURRENT[step]) == point["id"]
            ):
                if point["id"] == "mira":
                    point["action"] = "dialogue"
                elif point["id"] == "forge":
                    point["action"] = "forge"
                elif (
                    point["id"] == "clearing_fight"
                    and step == "clearing"
                    or point["id"] == "hunt"
                    and step == "hunt"
                    or point["id"] == "training"
                    and step in ("craft", "travel")
                ):
                    point["action"] = "explore"
        places.append(place)
    routes = _visible_routes(known, step, fighting, moving)
    bestiary = []
    if "goblin" in mobs:
        advantages = goblin_table["advantage"]
        bestiary.append(
            {
                "id": "goblin",
                "rank": "D",
                "name": "Gobelin des bois",
                "description": "Un adversaire simple rencontré dans la clairière et la lisière.",
                "hp": {
                    "first_encounter": GOBLIN["hp_first"],
                    "hunt": GOBLIN["hp_hunt"],
                },
                "stats": {
                    key: goblin_table["base_stats"][key]
                    for key in ("force", "endurance", "intelligence", "sagesse")
                },
                "weaknesses": [value.name for value in advantages["weakness"]],
                "resistances": [value.name for value in advantages["resilience"]],
                "loot": [
                    {"item": key, "quantity": quantity}
                    for key, quantity in GOBLIN["loot"].items()
                ],
                "rare_loot": [
                    {"item": key, "chance": value} for key, value in RARE_DROPS.items()
                ],
                "spawn_maps": [
                    {"id": key, "name": point_name(key)}
                    for key in party.get("seen_spawnpoints", ["clearing"])
                    if zone_of(key) in visited
                ],
                "xp": {
                    "first_encounter": GOBLIN["xp_first"],
                    "hunt": GOBLIN["xp_hunt"],
                    "training": 0,
                },
                "locations": [
                    PLACES[key]["name"] for key in sorted(visited) if key in PLACES
                ],
                "materials_usage": "Deux peaux et trois crocs permettent de fabriquer une veste à Rosée. L'entraînement ne donne aucun butin.",
            }
        )
    from .fields import MAPS
    from .map_building import MOBS, spawners, species_details
    from .mob_rules import resolve

    for identifier in MOBS:
        definition = resolve(MOBS, identifier)
        if identifier == "goblin" or identifier not in mobs:
            continue
        details = species_details(identifier)
        spawn_maps = [
            {"id": key, "name": point_name(key)}
            for key in party.get("seen_spawnpoints", [])
            if key in MAPS
            and zone_of(key) in visited
            and any(config["mob_id"] == identifier for config in spawners(MAPS[key]))
        ]
        bestiary.append(
            {
                "id": identifier,
                "rank": definition["rank"],
                "name": definition["name"],
                "description": "Statistiques de base au niveau 1 ; le niveau dépend du spawner ou de la zone.",
                "hp": {"first_encounter": details["hp"], "hunt": details["hp"]},
                "stats": details["stats"],
                "weaknesses": details["weaknesses"],
                "resistances": details["resistances"],
                "loot": [
                    {"item": key, "quantity": value}
                    for key, value in definition.get("loot", {}).items()
                ],
                "rare_loot": [
                    {"item": key, "chance": value} for key, value in RARE_DROPS.items()
                ],
                "spawn_maps": spawn_maps,
                "locations": [item["name"] for item in spawn_maps],
                "xp": {"first_encounter": 50, "hunt": 50, "training": 0},
                "materials_usage": "Matériaux communs utilisés par les recettes de forge.",
            }
        )
    from .mob_rules import drop_rules, experience, resolve

    for creature in bestiary:
        definition = resolve(MOBS, creature["id"])
        rules = drop_rules(definition, RARE_DROPS)
        creature["loot"] = [
            {
                "item": rule["item"],
                "quantity": rule["min"],
                "chance": rule["chance"],
                "attempts": rule["attempts"],
                "max_quantity": rule["max"],
            }
            for rule in rules
            if not rule.get("rare")
        ]
        creature["rare_loot"] = [
            {
                "item": rule["item"],
                "chance": rule["chance"],
                "attempts": rule["attempts"],
                "min": rule["min"],
                "max": rule["max"],
            }
            for rule in rules
            if rule.get("rare")
        ]
        if "hp" in definition.get("stats", {}):
            hp = round(definition["stats"]["hp"]["base"])
            creature["hp"] = {"first_encounter": hp, "hunt": hp}
        from .skill_catalog import library, mob_ability

        available = library(content.DATA, MOBS)
        creature["abilities"] = [
            mob_ability(available[item["skill_id"]], item)
            if "skill_id" in item
            else deepcopy(item)
            for item in definition.get("abilities", [])
        ]
        creature["xp"] = {
            "first_encounter": experience(
                {**definition, "level": 1}, 1, content.WORLD["mob_xp"]
            ),
            "hunt": experience({**definition, "level": 1}, 1, content.WORLD["mob_xp"]),
            "training": 0,
        }
        creature["spawn_maps"] = [
            item
            for item in creature["spawn_maps"]
            if item["id"] not in MAPS
            or any(
                config["mob_id"] == creature["id"]
                for config in spawners(MAPS[item["id"]])
            )
        ]
    current_zone = zone_of(party.get("position", CURRENT[step]))
    if current_zone not in {p["id"] for p in places}:
        definition = PLACES[current_zone]
        places.append({"id": current_zone, **deepcopy(definition), "visited": True})
    return {
        "current": zone_of(party.get("position", CURRENT[step])),
        "position": party.get("position", CURRENT[step]),
        "places": places,
        "routes": routes,
        "graph": graph(known),
        "zone_entries": ZONE_ENTRIES,
        "bestiary": bestiary,
        "objectives": [
            {"zone": zone, "point": point["id"], "x": place["x"], "y": place["y"]}
            for zone, place in PLACES.items()
            for point in place["points"]
            if any(quest.get("npc") == point["id"] for quest in content.DATA["quests"])
        ],
    }


ROAD_POINTS = {
    route["id"]: {"zone": route["from"], "name": route["name"]} for route in ROUTES
}


def map_for_point(point):
    if point in WORLD_MAP_DATA:
        return point
    return POINT_MAPS.get(point, ZONE_ENTRIES.get(point))


def travel_entry(source, destination):
    return deepcopy(EDGES.get(source, {}).get(destination, {}).get("entry"))


def migrate_journey(party):
    """Recover saves on deleted Builder points without resurrecting geography."""
    transit = party.get("transit") or {}
    points = [party.get("position"), *party.get("journey", [])]
    points.extend(
        transit.get(key) for key in ("source", "destination") if key in transit
    )
    if all(zone_of(point) is not None for point in points):
        return
    candidates = [
        party.get("field_map"),
        party.get("position"),
        transit.get("source"),
        party.get("field_return_from"),
        content.gameplay()["rules"]["start"]["map"],
    ]
    party["position"] = next(
        point for point in candidates if zone_of(point) is not None
    )
    party.update(journey=[], transit=None)
    party["visited"] = [
        point for point in party.get("visited", []) if zone_of(point) is not None
    ]


def zone_of(point):
    if point in WORLD_MAP_DATA:
        from .map_building import zone_of as map_zone

        return map_zone(WORLD_MAP_DATA, point)
    if point in ROAD_POINTS:
        return zone_of(ROAD_POINTS[point]["zone"])
    if point in PLACES:
        return point
    owner = POINT_MAPS.get(point)
    return zone_of(owner) if owner else None


def point_name(point):
    if point in ROAD_POINTS:
        return ROAD_POINTS[point]["name"]
    if point in WORLD_MAP_DATA:
        return WORLD_MAP_DATA[point]["name"]
    zone = zone_of(point)
    if point == zone:
        return PLACES[zone]["name"]
    return next(p["name"] for p in PLACES[zone]["points"] if p["id"] == point)


def hazard(point):
    if point in ROAD_POINTS:
        route = next(route for route in ROUTES if route["id"] == point)
        return route.get("hazard", True)
    definition = WORLD_MAP_DATA.get(map_for_point(point), {})
    return bool(definition.get("spawners") or definition.get("spawns"))


def graph(known):
    # Initialize once; never overwrite a node while visiting another zone.
    known = set(known)
    nodes = {node for node in EDGES if zone_of(node) in known}
    nodes.update(
        target
        for source in tuple(nodes)
        for target in EDGES[source]
        if zone_of(target) in known
    )
    return {
        node: sorted(target for target in EDGES.get(node, {}) if target in nodes)
        for node in sorted(nodes)
    }


def validate_path(start, destination, known, proposed):
    if (
        not isinstance(destination, str)
        or zone_of(destination) not in known
        or not isinstance(proposed, list)
    ):
        return False
    nodes = graph(known)
    if len(proposed) > len(nodes) or not all(
        isinstance(point, str) for point in proposed
    ):
        return False
    if len(set(proposed)) != len(proposed) or start in proposed:
        return False
    previous = start
    for point in proposed:
        if point not in nodes.get(previous, []):
            return False
        previous = point
    return previous == destination


def path(start, destination, known):
    if not isinstance(destination, str) or zone_of(destination) not in known:
        return None
    nodes = graph(known)
    queue = [(start, [])]
    visited = set()
    for node, route in queue:
        if node == destination:
            return route
        if node in visited:
            continue
        visited.add(node)
        queue.extend(
            (neighbor, route + [neighbor])
            for neighbor in nodes.get(node, [])
            if neighbor not in visited
        )
    return None


def dungeon_detours(start, destination, route):
    """Prefer outdoor itineraries when neither endpoint is in a dungeon."""

    def dungeon(point):
        return (WORLD_MAP_DATA.get(map_for_point(point), {}).get("dungeon") or {}).get(
            "id"
        )

    allowed = {dungeon(start), dungeon(destination)}
    return len({point for point in route if dungeon(point) not in allowed})


def distance_km(source, destination):
    road = (
        source
        if source in ROAD_POINTS
        else destination
        if destination in ROAD_POINTS
        else None
    )
    if road:
        return next(r["distance_km"] for r in ROUTES if r["id"] == road) / 2
    return 0.01


def walking_seconds(source, destination):
    edge = EDGES.get(source, {}).get(destination, {})
    if edge.get("seconds") is not None:
        return edge["seconds"]
    return (
        distance_km(source, destination)
        / content.DATA["gameplay"]["rules"]["movement"]["walking_kmh"]
        * 3600
    )
