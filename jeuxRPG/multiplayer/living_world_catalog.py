"""Build living-world geography from the selected Builder catalogue."""

import hashlib
import json
from copy import deepcopy

DEFAULT_RULES = {
    "economy_period": 900,
    "patrol_period": 900,
    "raid_period": 7200,
    "raid_warning": 300,
    "raid_duration": 180,
    "merchant_stay": 28800,
    "npc_cycle": 3600,
    "event_budget": 128,
    "history_limit": 40,
}


def fingerprint(catalog):
    return hashlib.sha256(
        json.dumps(
            catalog, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def build_catalog(seed="jeux-rpg-living-world-v1", speed=1):
    from . import economy, tactics, world

    speed = float(speed)
    maps = {}
    for key, definition in sorted(world.WORLD_MAP_DATA.items()):
        # Region diagrams are not physical maps.
        if not definition.get("width") or not definition.get("height"):
            continue
        candidates = [
            tuple(p)
            for p in definition.get("paths", [])
            if tactics.walkable(definition, p)
        ]
        if not candidates:
            candidates = [
                (x, y)
                for y in range(1, definition["height"] - 1)
                for x in range(1, definition["width"] - 1)
                if tactics.walkable(definition, [x, y])
            ]
        if not candidates:
            continue
        # A caravan stall must not occupy a map exit: entering that tile would
        # immediately send the player back to the regional map.
        exits = {tuple(gate["position"]) for gate in definition.get("exits", [])}
        interior = [
            point
            for point in candidates
            if 0 < point[0] < definition["width"] - 1
            and 0 < point[1] < definition["height"] - 1
            and point not in exits
        ]
        start = (interior or candidates)[0]
        goal = max(
            candidates, key=lambda p: abs(p[0] - start[0]) + abs(p[1] - start[1])
        )
        route = tactics.path(definition, list(start), list(goal)) or []
        maps[key] = {
            "id": key,
            "display_id": definition["id"],
            "name": definition["name"],
            "zone": world.zone_of(key),
            "route": [list(start), *route],
            "town": definition.get("biome") in ("village", "town", "city"),
        }
        if definition.get("settlement"):
            maps[key].update(
                settlement=definition["settlement"],
                garrison=True,
                town=key == definition["settlement"],
            )
    towns = {
        key: {"id": key, "name": value["name"], "zone": value["zone"]}
        for key, value in maps.items()
        if value["town"]
    }
    journeys = {}
    for source in towns:
        journeys[source] = {}
        for target in towns:
            if source == target:
                continue
            route = world.path(source, target, set(world.PLACES))
            if route is None:
                continue
            points = [source, *route]
            duration = sum(
                world.walking_seconds(a, b)
                for a, b in zip(points, points[1:], strict=False)
            )
            journeys[source][target] = {"duration": max(1, duration), "points": points}
    graph = world.graph(set(world.PLACES))
    neighbours = {}
    for source in maps:
        found, visited, queue = set(), {source}, list(graph.get(source, []))
        while queue:
            point = queue.pop(0)
            if point in visited:
                continue
            visited.add(point)
            if point in maps:
                found.add(point)
            else:
                queue.extend(graph.get(point, []))
        neighbours[source] = sorted(found)
    goods = {
        key: {"name": item["name"], "buy": int(item["buy"]), "sell": int(item["sell"])}
        for key, item in sorted(economy.prices().items())
        if item.get("buy", 0) > 0 and 0 <= item.get("sell", 0) <= item["buy"]
    }
    # A small stock prevents the shared-world payload from growing with every item.
    goods = dict(list(goods.items())[:8])
    result = {
        "version": 1,
        "seed": seed,
        "speed": speed,
        "rules": deepcopy(DEFAULT_RULES),
        "maps": maps,
        "towns": towns,
        "journeys": journeys,
        "neighbours": neighbours,
        "goods": goods,
    }
    previous = world.WORLD_MAP_DATA.get("clearing", {}).get("previous_world_catalogs")
    if previous:
        result["previous_catalogs"] = list(previous)
    return result
