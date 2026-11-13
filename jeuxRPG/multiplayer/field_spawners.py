"""Apply Builder spawn edits to visited fields without resetting character progress."""

import hashlib
import json

from . import map_building, mob_rules


def manifest(definition, maps, identifier):
    result = {}
    for index, config in enumerate(map_building.spawners(definition)):
        species = mob_rules.resolve(map_building.MOBS, config["mob_id"])
        payload = [config, species, map_building.map_level(maps, identifier)]
        result[f"{identifier}-mob-{index}"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
    return result


def origin(mob):
    return mob.get("combat_id", "").split(":repop:", 1)[0]


def sync(party, identifier, now):
    from . import fields, tutorial

    battle = party["battle"]
    definition = fields.MAPS[identifier]
    current = manifest(definition, fields.MAPS, identifier)
    previous = battle.get("spawn_manifest")
    if previous is None:
        # Legacy saves retain the original encounter size, including slain mobs.
        # An old empty field therefore receives every newly authored spawner.
        previous = {
            key: current.get(key, "retired")
            for index in range(battle.get("initial_mobs", len(party["mobs"])))
            for key in [f"{identifier}-mob-{index}"]
        }
    if previous == current:
        battle["spawn_manifest"] = current
        return
    unchanged = {key for key in previous if previous[key] == current.get(key)}
    changed = (set(previous) | set(current)) - unchanged
    removed = {mob["combat_id"] for mob in party["mobs"] if origin(mob) in changed}
    party["mobs"] = [mob for mob in party["mobs"] if origin(mob) not in changed]
    battle["arrivals"] = [
        arrival
        for arrival in battle.get("arrivals", [])
        if origin(arrival["mob"]) not in changed
    ]
    for unit in [*battle["players"].values(), *battle.get("summons", {}).values()]:
        if (unit.get("casting") or {}).get("target") in removed:
            unit.pop("casting", None)
        if (unit.get("order") or {}).get("target") in removed:
            unit["order"] = {"type": "hold"}
    fields.repop(party, identifier, now, skip_origins=unchanged)
    identifiers = [mob["combat_id"] for mob in party["mobs"]]
    for mob in party["mobs"]:
        mob["allies"] = [key for key in identifiers if key != mob["combat_id"]]
    tutorial.sync_mobs(party)
    battle["spawn_manifest"] = current
    battle["next_brain"] = min(battle.get("next_brain", now), now)
    fields.reveal(party)
