"""Physical exits between logical zones, shared by atlas and local maps."""

from .map_building import zone_of


def passages(maps, source):
    data = maps[source]
    logical = maps.get("clearing", {}).get("logical_zones", {})
    result = []
    for index, gate in enumerate(data.get("exits", [])):
        target = gate.get("destination")
        if target not in maps or zone_of(maps, source) == zone_of(maps, target):
            continue
        zone = zone_of(maps, target)
        result.append(
            {
                "id": f"{source}:{index}",
                "source": source,
                "source_name": data["name"],
                "position": gate["position"][:],
                "destination": target,
                "destination_name": maps[target]["name"],
                "zone": zone,
                "zone_name": logical.get(zone, maps.get(zone, maps[target]))["name"],
                "name": gate.get("name", maps[target]["name"]),
            }
        )
    return result


def zone_passages(maps, zone):
    return [
        p for key in maps if zone_of(maps, key) == zone for p in passages(maps, key)
    ]
