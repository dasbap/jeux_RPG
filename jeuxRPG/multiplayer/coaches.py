"""Directed stagecoach services; boarding rights belong to departure stops."""

import math
from copy import deepcopy


def validate_data(gameplay):
    stations, routes = gameplay["coach_stations"], gameplay["coach_routes"]
    if (
        not isinstance(stations, dict)
        or len(stations) > 100
        or not isinstance(routes, dict)
        or len(routes) > 200
    ):
        raise ValueError("Diligences : catalogue invalide.")
    from .gameplay_catalog import identifier

    for key, station in stations.items():
        if (
            not identifier(key)
            or not isinstance(station, dict)
            or set(station) != {"name", "map", "position", "boarding"}
            or not isinstance(station["name"], str)
            or not 1 <= len(station["name"]) <= 100
            or not isinstance(station["map"], str)
            or type(station["boarding"]) is not bool
            or not isinstance(station["position"], list)
            or len(station["position"]) != 2
            or any(type(n) is not int or n < 0 for n in station["position"])
        ):
            raise ValueError("Diligence : arrêt invalide.")
    for key, route in routes.items():
        if (
            not identifier(key)
            or not isinstance(route, dict)
            or set(route) != {"name", "from", "to", "duration_seconds"}
            or not isinstance(route["name"], str)
            or not 1 <= len(route["name"]) <= 100
            or not isinstance(route.get("from"), str)
            or not isinstance(route.get("to"), str)
            or route.get("from") not in stations
            or route.get("to") not in stations
            or route["from"] == route["to"]
            or not stations[route["from"]]["boarding"]
            or type(route["duration_seconds"]) not in (int, float)
            or not math.isfinite(route["duration_seconds"])
            or not 1 <= route["duration_seconds"] <= 300
        ):
            raise ValueError("Diligence : ligne ou départ invalide.")


def validate_references(gameplay, maps):
    from . import tactics

    for key, station in gameplay["coach_stations"].items():
        data = maps.get(station["map"])
        if not data or not tactics.walkable(data, station["position"]):
            raise ValueError("Diligence : arrêt hors carte ou impraticable.")
        if not any(
            site["id"] == key and site["position"] == station["position"]
            for site in data.get("sites", [])
        ):
            raise ValueError(
                "Diligence : placez le lieu correspondant à cet arrêt sur sa carte."
            )
        if station["position"] in [gate["position"] for gate in data["exits"]]:
            raise ValueError("Diligence : un arrêt ne peut pas occuper une sortie.")


def enabled():
    from . import fields

    return fields.MAPS["clearing"].get("seamless_transitions", False)


def settings():
    from . import content

    return content.gameplay()


def view(party, player):
    data = settings()
    stations = data.get("coach_stations", {})
    nearby = []
    unit = (party.get("battle") or {}).get("players", {}).get(player)
    for key, station in stations.items():
        if (
            unit
            and station["map"] == party.get("field_map")
            and math.dist(unit["position"], station["position"]) <= 2
        ):
            nearby.append(
                {
                    "id": key,
                    **deepcopy(station),
                    "routes": [
                        {
                            "id": route_id,
                            "name": route["name"],
                            "destination": stations[route["to"]]["name"],
                            "arrival_only": not stations[route["to"]]["boarding"],
                            "duration_seconds": route["duration_seconds"],
                        }
                        for route_id, route in data["coach_routes"].items()
                        if route["from"] == key
                    ],
                }
            )
    return {
        "enabled": enabled(),
        "nearby": nearby,
        "locked_reason": lock_reason(party, player),
    }


def lock_reason(party, player):
    from . import mob_rules

    unit = (party.get("battle") or {}).get("players", {}).get(player, {})
    if (
        party.get("transit")
        or not unit
        or party["characters"][player]["stats"]["hp"]["current"] <= 0
        or unit.get("casting")
    ):
        return "Arrêtez-vous au relais, vivant et sans incantation."
    if any(
        mob_rules.is_hostile(mob) and mob.get("alerted")
        for mob in party.get("mobs", [])
    ):
        return "Les ennemis vous poursuivent : impossible de monter en diligence."
    return ""


def depart(party, player, station_id, route_id, now, error):
    from . import fields, progression

    if not isinstance(station_id, str) or not isinstance(route_id, str):
        raise error("invalid_coach", "Diligence inconnue.", 409)
    data = settings()
    station = data.get("coach_stations", {}).get(station_id)
    route = data.get("coach_routes", {}).get(route_id)
    if (
        not enabled()
        or not station
        or not route
        or route["from"] != station_id
        or not station["boarding"]
    ):
        raise error(
            "invalid_coach",
            "Aucune diligence ne part de cet arrêt vers cette destination.",
            409,
        )
    unit = (party.get("battle") or {}).get("players", {}).get(player)
    if (
        not unit
        or party.get("field_map") != station["map"]
        or math.dist(unit["position"], station["position"]) > 2
    ):
        raise error(
            "wrong_location", "Approchez-vous du relais pour monter en diligence.", 409
        )
    reason = lock_reason(party, player)
    if reason:
        raise error("coach_unavailable", reason, 409)
    for key, actor in party["characters"].items():
        other = party["battle"]["players"].get(key)
        if actor["stats"]["hp"]["current"] > 0 and (
            not other or math.dist(other["position"], station["position"]) > 3
        ):
            raise error(
                "party_not_ready", "Rassemblez vos compagnons près du relais.", 409
            )
    target = data["coach_stations"][route["to"]]
    duration = route["duration_seconds"] * progression.RATIO
    party.setdefault("fields", {})[station["map"]] = fields.snapshot(
        party, now, party["mobs"]
    )
    party["linked_companions"] = deepcopy(party["battle"].get("companions", {}))
    party.update(battle=None, mobs=[], mob=None, journey=[], field_mode=True)
    party.pop("field_map", None)
    party["transit"] = {
        "mode": "coach",
        "station": station_id,
        "arrival_station": route["to"],
        "name": route["name"],
        "source": station["map"],
        "destination": target["map"],
        "field_entry": target["position"][:],
        "remaining": duration,
        "total": duration,
        "segment": duration,
        "started_at": now,
        "ready_at": now + duration,
        "hazard": False,
    }
    return [f"La diligence part vers {target['name']}."], False


def restore_field(party, now):
    """Resume legacy world-map saves directly on their physical sector."""
    from . import content, fields, world

    if (
        not enabled()
        or not party.get("field_mode")
        or party.get("field_map")
        or party.get("battle")
        or party.get("transit")
    ):
        return
    identifier = world.map_for_point(party["position"])
    if identifier not in fields.MAPS:
        identifier = content.gameplay()["rules"]["start"]["map"]
    site = next(
        (
            s
            for s in fields.MAPS[identifier].get("sites", [])
            if s["id"] == party["position"]
        ),
        None,
    )
    fields.enter(
        party,
        identifier,
        site["position"] if site else fields.arrival_point(identifier),
        now,
    )
