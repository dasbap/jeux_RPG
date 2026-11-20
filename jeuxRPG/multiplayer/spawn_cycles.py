"""Persistent staggered replenishment of physical Builder spawners."""

import math
from collections import defaultdict

PRESETS = {
    "default": {"name": "Standard", "seconds": 120},
    "warrior": {"name": "Guerrier", "seconds": 120},
    "archer": {"name": "Archer", "seconds": 120},
    "mage": {"name": "Mage", "seconds": 150},
    "elite": {"name": "\u00c9lite", "seconds": 240},
    "boss": {"name": "Boss", "seconds": 600},
    "civilian": {"name": "Civil / neutre", "seconds": 120},
    "never": {"name": "Aucune r\u00e9apparition", "seconds": 0},
}


def profiles():
    from . import content

    return content.gameplay().get("respawn_profiles", {})


def validate_profiles(data):
    from .gameplay_catalog import identifier

    if not isinstance(data, dict) or len(data) > 40 or (data and "default" not in data):
        raise ValueError("Profils de r\u00e9apparition : profil default requis.")
    for key, value in data.items():
        if (
            not identifier(key)
            or not isinstance(value, dict)
            or set(value) != {"name", "seconds"}
            or not isinstance(value["name"], str)
            or not 1 <= len(value["name"]) <= 100
            or type(value["seconds"]) not in (int, float)
            or not math.isfinite(value["seconds"])
            or not 0 <= value["seconds"] <= 86400
        ):
            raise ValueError(
                "Profil de r\u00e9apparition invalide (0 = d\u00e9sactiv\u00e9)."
            )


def validate_spawner(config):
    from .gameplay_catalog import identifier

    if "respawn_profile" in config and not identifier(config["respawn_profile"]):
        raise ValueError("Profil de spawner invalide.")
    value = config.get("respawn_seconds")
    if value is not None and (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 <= value <= 86400
    ):
        raise ValueError(
            "R\u00e9apparition : 0 \u00e0 86400 secondes r\u00e9elles, ou vide pour h\u00e9riter."
        )


def groups(identifier, definition):
    from .map_building import spawners
    from .progression import RATIO

    result = defaultdict(lambda: {"origins": []})
    for index, config in enumerate(spawners(definition)):
        group = result[str(tuple(config["position"]))]
        group["origins"].append(f"{identifier}-mob-{index}")
        group["config"] = config
    for group in result.values():
        config = group["config"]
        seconds = config.get("respawn_seconds")
        if seconds is None:
            seconds = profiles().get(
                config.get("respawn_profile", "default"),
                profiles().get("default", {"seconds": 120}),
            )["seconds"]
        group["interval"] = seconds * RATIO / len(group["origins"])
    return result


def on_death(party, mob, now):
    if not profiles() or not party.get("field_map") or party.get("training"):
        return
    from . import fields
    from .field_spawners import origin

    identifier = origin(mob).rsplit("-mob-", 1)[0]
    if identifier not in fields.MAPS:
        return
    for key, group in groups(identifier, fields.MAPS[identifier]).items():
        if origin(mob) in group["origins"] and group["interval"]:
            party.setdefault("spawn_timers", {}).setdefault(identifier, {}).setdefault(
                key, {"next_at": now + group["interval"], "interval": group["interval"]}
            )


def alive_origins(party):
    from .field_spawners import origin

    result = set()
    for snapshot in [party, *party.get("fields", {}).values()]:
        result.update(
            origin(m)
            for m in snapshot.get("mobs", [])
            if m["stats"]["hp"]["current"] > 0
        )
        result.update(
            origin(a["mob"]) for a in (snapshot.get("battle") or {}).get("arrivals", [])
        )
    return result


def advance(party, identifier, now):
    if not profiles() or party.get("training"):
        return
    from . import fields

    timers = party.setdefault("spawn_timers", {}).setdefault(identifier, {})
    current = groups(identifier, fields.MAPS[identifier])
    for key in list(timers):
        if key not in current:
            timers.pop(key)
    alive = alive_origins(party)
    wanted = set()
    for key, group in current.items():
        missing = [o for o in group["origins"] if o not in alive]
        interval = group["interval"]
        if not missing or not interval:
            timers.pop(key, None)
            continue
        timer = timers.get(key)
        if timer is None or timer["interval"] != interval:
            timer = timers[key] = {"next_at": now + interval, "interval": interval}
        if now < timer["next_at"]:
            continue
        count = min(len(missing), int((now - timer["next_at"]) / interval) + 1)
        wanted.update(missing[:count])
        timer["next_at"] += count * interval
        if count == len(missing):
            timers.pop(key, None)
    if wanted:
        all_origins = {o for g in current.values() for o in g["origins"]}
        fields.repop(
            party,
            identifier,
            now,
            skip_origins=all_origins - wanted,
            refresh_encounter=False,
        )


def validate_references(maps, gameplay):
    settings = gameplay["respawn_profiles"]
    for data in maps.values():
        for spawn in data.get("spawners", []):
            if settings and spawn.get("respawn_profile", "default") not in settings:
                raise ValueError("Profil de réapparition inconnu.")
