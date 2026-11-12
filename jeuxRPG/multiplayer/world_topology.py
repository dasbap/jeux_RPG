"""World navigation compiled exclusively from the Builder catalogue.

Logical zones group maps for display. They never connect unrelated maps.
"""

from copy import deepcopy
from itertools import pairwise

from .map_building import zone_of
from .map_layout_editor import apply_layout, layout_places


def compile_world(maps):
    logical = maps.get("clearing", {}).get("logical_zones", {})
    places = layout_places(maps)
    streets = {
        key: deepcopy(data["village_streets"])
        for key, data in maps.items()
        if "village_streets" in data
    }
    routes = deepcopy(maps.get("clearing", {}).get("travel_routes", []))
    levels, owners, entries, edges = {}, {}, {}, {}

    def connect(source, target, seconds=None, entry=None):
        edges.setdefault(source, {})[target] = {
            "seconds": seconds,
            "entry": deepcopy(entry),
        }

    for zone, place in places.items():
        data = logical.get(zone, maps.get(zone, {}))
        place.update(
            type="village" if data.get("biome") == "village" else "zone",
            description=data.get("description", data["name"]),
        )
        levels[zone] = data.get("level", data.get("zone_level", 1))
        members = [key for key in maps if zone_of(maps, key) == zone]
        # Selecting a zone addresses its first map; it does not join every map.
        if members:
            entries[zone] = zone if zone in maps else members[0]
        place["points"] = [point for point in place["points"] if point["id"] != zone]

    for key, data in maps.items():
        zone = zone_of(maps, key)
        place = places[zone]
        edges.setdefault(key, {})
        points = {}
        for site in data.get("sites", []):
            point = {
                "id": site["id"],
                "name": site["name"],
                "type": "indice"
                if site.get("interaction") == "inspect"
                else "pnj"
                if site.get("dialogue")
                else "atelier",
                "description": site.get("dialogue", site["name"]),
            }
            points[point["id"]] = point
        layout = streets.get(key)
        if layout:
            points.setdefault(
                layout["square"],
                {
                    "id": layout["square"],
                    "name": layout["square"],
                    "type": "repère",
                    "description": "Place centrale.",
                },
            )
            chains = [[key, layout["square"]]]
            for street in layout["streets"]:
                points[street["id"]] = {
                    "id": street["id"],
                    "name": street["name"],
                    "type": "rue",
                    "description": street["name"],
                }
                for building in street["buildings"]:
                    points.setdefault(
                        building,
                        {
                            "id": building,
                            "name": building,
                            "type": "bâtiment",
                            "description": building,
                        },
                    )
                chains.append([layout["square"], street["id"], *street["buildings"]])
            connected = {node for chain in chains for node in chain}
            chains.extend([key, point] for point in points if point not in connected)
        else:
            chains = [[key, point] for point in points]
        for chain in chains:
            for source, target in pairwise(chain):
                connect(source, target)
                connect(target, source)
        for point in points.values():
            owners[point["id"]] = key
            place["points"].append(point)
        # A passage is directional unless a reverse gate is also authored.
        for gate in data.get("exits", []):
            target = gate.get("destination")
            if target in maps:
                connect(key, target, gate.get("travel_minutes", 0) * 60, gate["entry"])

    for zone, entry in entries.items():
        if zone != entry:
            connect(zone, entry, 0)
            connect(entry, zone, 0)
    for route in routes:
        middle, source, target = route["id"], route["from"], route["to"]
        connect(source, middle)
        connect(middle, target)
        if route.get("bidirectional", True):
            connect(target, middle)
            connect(middle, source)

    apply_layout(places, {**maps, **logical})
    return places, streets, routes, levels, owners, entries, edges
