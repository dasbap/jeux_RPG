"""Bounded visual cues emitted only after authoritative combat decisions."""

from copy import deepcopy


def position(party, identifier):
    battle = party.get("battle") or {}
    units = {
        **battle.get("players", {}),
        **battle.get("summons", {}),
        **battle.get("companions", {}),
        **battle.get("guard_patrol", {}).get("members", {}),
    }
    unit = units.get(identifier) or next(
        (mob for mob in party.get("mobs", []) if mob["combat_id"] == identifier), None
    )
    return deepcopy(unit["position"]) if unit else None


def emit(
    party,
    actor,
    target,
    now,
    kind="strike",
    skill_type="DAMAGE",
    name="",
    reach=1.5,
    amount=0,
    duration=0,
):
    battle = party.get("battle")
    source, destination = position(party, actor), position(party, target)
    if not battle or source is None or destination is None:
        return
    sequence = battle.get("visual_sequence", 0) + 1
    battle["visual_sequence"] = sequence
    events = [
        event for event in battle.get("visual_events", []) if event["at"] >= now - 12
    ]
    events.append(
        {
            "id": sequence,
            "at": now,
            "actor": actor,
            "target": target,
            "source": source,
            "destination": destination,
            "kind": kind,
            "type": skill_type,
            "name": name[:80],
            "range": reach,
            "amount": round(amount, 2),
            "duration": duration,
        }
    )
    battle["visual_events"] = events[-32:]


def public(party, player, now):
    from . import tactics

    battle = party["battle"]
    unit = battle["players"].get(player) if player else None
    enemies = {mob["combat_id"]: mob for mob in party.get("mobs", [])}
    preset = tactics.PRESETS[battle["preset"]]
    return [
        deepcopy(event)
        for event in battle.get("visual_events", [])
        if now - event["at"] <= 12
        and (
            unit is None
            or event["actor"] not in enemies
            or tactics.visible(party, player, enemies[event["actor"]])
        )
        and (
            unit is None
            or all(
                tactics.distance(unit["position"], event[key]) <= tactics.PLAYER_VISION
                and tactics.sight(preset, unit["position"], event[key])
                for key in ("source", "destination")
            )
        )
    ]
