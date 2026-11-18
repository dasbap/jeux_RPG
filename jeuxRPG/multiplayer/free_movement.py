"""Continuous movement, with server-timed speed validation of client positions."""

import math
from copy import deepcopy

RADIUS = 0.22
HEARTBEAT = 1.2  # game seconds; expired input never moves a disconnected player
MAX_CATCHUP = 0.75
ATTACK_SLOW_FACTOR = 0.55
ATTACK_RECOVERY = 1.35  # game seconds, 0.45 real seconds
POSITION_JITTER = 3.0  # game seconds: at most one real second of unused credit


def cell(position):
    return [math.floor(value + 0.5) for value in position]


def finite_pair(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
    )


def obstacles(preset):
    solids = {tuple(p) for p in (*preset["cover"], *preset.get("blocked", []))}
    solids.update(
        tuple(p) for p in preset.get("water", []) if p not in preset.get("bridges", [])
    )
    return solids


def fits(preset, position, solids=None):
    if not finite_pair(position):
        return False
    x, y = position
    if not (
        -0.5 + RADIUS <= x <= preset["width"] - 0.5 - RADIUS
        and -0.5 + RADIUS <= y <= preset["height"] - 0.5 - RADIUS
    ):
        return False
    solids = obstacles(preset) if solids is None else solids
    for px in range(math.floor(x - RADIUS + 0.5), math.floor(x + RADIUS + 0.5) + 1):
        for py in range(math.floor(y - RADIUS + 0.5), math.floor(y + RADIUS + 0.5) + 1):
            if (px, py) not in solids:
                continue
            near_x, near_y = (
                max(px - 0.5, min(px + 0.5, x)),
                max(py - 0.5, min(py + 0.5, y)),
            )
            if (x - near_x) ** 2 + (y - near_y) ** 2 < RADIUS**2 - 1e-9:
                return False
    return True


def segment(preset, source, target, solids=None):
    if not finite_pair(target):
        return False
    distance = math.dist(source, target)
    if distance > 2:
        return False
    count = max(1, math.ceil(distance / 0.10))
    solids = obstacles(preset) if solids is None else solids
    return all(
        fits(
            preset,
            [a + (b - a) * i / count for a, b in zip(source, target, strict=True)],
            solids,
        )
        for i in range(1, count + 1)
    )


def command(party, player, action, params, now, error):
    from . import tactics

    actor = tactics.ready(party, player, now, error, redirect=True, moving_cast=True)
    unit = party["battle"]["players"][player]
    preset = tactics.PRESETS[party["battle"]["preset"]]
    if action == "move_axis":
        axis = [params["x"], params["y"]]
        if not finite_pair(axis) or any(abs(v) > 1 for v in axis):
            raise error("invalid_direction", "Direction invalide.")
        length = math.hypot(*axis)
        direction = [v / max(1, length) for v in axis]
        route = []
    else:
        route = params["path"]
        target = [params["x"], params["y"]]
        if (
            not finite_pair(target)
            or not isinstance(route, list)
            or not route
            or len(route) > min(2048, preset["width"] * preset["height"])
            or route[-1] != target
        ):
            raise error("invalid_path", "Trajet invalide.")
        previous = unit["position"]
        solids = obstacles(preset)
        for point in route:
            if not segment(preset, previous, point, solids):
                raise error("invalid_path", "Trajet bloqué ou vitesse impossible.")
            previous = point
        direction = [0, 0]
    # Validation is complete before the old order is changed.
    if action == "move_axis" and "position" in params:
        if not report_position(
            unit,
            preset,
            actor,
            params["position"],
            now,
            error,
            params.get("position_seq"),
        ):
            return []
    else:
        advance(unit, preset, actor, now)
        unit.pop("position_client", None)
    unit.update(
        free_motion=True,
        motion_axis=direction,
        motion_until=now + HEARTBEAT,
        motion_at=now,
        route=deepcopy(route),
        motion_speed=current_speed(unit, now),
    )
    party["battle"]["continuous_agents"] = True
    party["battle"].setdefault("agents_at", now)
    return []


def current_speed(unit, now):
    from . import tactics

    base = 1 / (tactics.STEALTH_MOVE_TIME if unit.get("hidden") else tactics.MOVE_TIME)
    until = max(
        unit.get("attack_slow_until", 0), (unit.get("casting") or {}).get("ends_at", 0)
    )
    return base * (ATTACK_SLOW_FACTOR if until > now else 1)


def position_budget(unit, now):
    """Accrue distance using server time, with a bounded allowance for packet jitter."""
    previous = unit.get("position_budget_at", now)
    elapsed = max(0, now - previous)
    base = current_speed(unit, float("inf"))
    slow_until = max(
        unit.get("attack_slow_until", 0), (unit.get("casting") or {}).get("ends_at", 0)
    )
    slow = min(elapsed, max(0, slow_until - previous))
    earned = base * (elapsed - slow + slow * ATTACK_SLOW_FACTOR)
    maximum = current_speed(unit, now) * POSITION_JITTER
    available = unit.get("position_budget", maximum) + earned
    # A delayed packet may cover more than a heartbeat of entirely legal travel.
    # Preserve that elapsed allowance while moving; cap unused credit at each
    # accepted report and while stopped, rather than capping the travel itself.
    unit["position_budget"] = (
        available if any(unit.get("motion_axis", [])) else min(maximum, available)
    )
    unit["position_budget_at"] = max(previous, now)


def report_position(unit, preset, actor, position, now, error, sequence=None):
    if sequence is not None:
        if type(sequence) is not int or not 1 <= sequence <= 9007199254740991:
            raise error("invalid_position", "Séquence de position invalide.")
        if sequence <= unit.get("position_sequence", 0):
            return False
    if not finite_pair(position):
        raise error("invalid_position", "Position invalide.")
    if not actor.is_alive() or actor.is_stunned():
        raise error("cannot_move", "Ce personnage ne peut pas se déplacer.")
    # A valid report is accepted exactly; there is no competing simulation.
    trial = deepcopy(unit)
    position_budget(trial, now)
    distance = math.dist(unit["position"], position)
    if distance > trial["position_budget"] + 1e-7:
        raise error("movement_speed", "Vitesse maximale dépassée.", 409)
    solids = obstacles(preset)
    if not fits(preset, position, solids):
        raise error("invalid_position", "Déplacement bloqué par le terrain.", 409)
    count = max(1, math.ceil(distance / 0.1))
    if not all(
        fits(
            preset,
            [
                a + (b - a) * i / count
                for a, b in zip(unit["position"], position, strict=True)
            ],
            solids,
        )
        for i in range(1, count + 1)
    ):
        raise error("invalid_position", "Déplacement bloqué par le terrain.", 409)
    unit.update(
        position=list(position),
        position_client=True,
        free_motion=True,
        position_budget=min(
            current_speed(unit, now) * POSITION_JITTER,
            max(0, trial["position_budget"] - distance),
        ),
        position_budget_at=trial["position_budget_at"],
        motion_at=now,
        position_reported_at=now,
    )
    if sequence is not None:
        unit["position_sequence"] = sequence
    return True


def report_attack_position(party, player, params, actor, now, error):
    if "position" not in params:
        return
    from . import tactics

    accepted = report_position(
        party["battle"]["players"][player],
        tactics.PRESETS[party["battle"]["preset"]],
        actor,
        params["position"],
        now,
        error,
        params.get("position_seq"),
    )
    if not accepted:
        raise error(
            "stale_position", "Position déjà mise à jour. Réessayez votre attaque.", 409
        )


def awaiting_position(unit, now, since):
    """Wait briefly for a moving client's report, never beyond input expiry."""
    return bool(
        unit.get("position_client")
        and any(unit.get("motion_axis", []))
        and now <= unit.get("motion_until", 0)
        and unit.get("position_reported_at", -1) < since
    )


def advance(unit, preset, actor, now):
    from . import tactics

    if not unit.get("free_motion"):
        return
    previous = unit.get("motion_at", now)
    unit["motion_at"] = max(previous, now)
    if not actor.is_alive() or actor.is_stunned():
        unit.update(motion_axis=[0, 0], route=[], motion_until=now)
        return
    if unit.get("position_client"):
        return
    if "position_budget_at" in unit:
        # Time already simulated by a legacy path cannot be spent a second time
        # as client-reported travel when switching back to free controls.
        unit["position_budget_at"] = max(unit["position_budget_at"], now)
    route = unit.get("route", [])
    until = now if route else min(now, unit.get("motion_until", previous))
    elapsed = min(MAX_CATCHUP, max(0, until - previous))
    speed = 1 / (tactics.STEALTH_MOVE_TIME if unit.get("hidden") else tactics.MOVE_TIME)
    slow_until = max(
        unit.get("attack_slow_until", 0), (unit.get("casting") or {}).get("ends_at", 0)
    )
    slow_elapsed = max(0, min(elapsed, slow_until - previous))
    unit["motion_speed"] = speed * (ATTACK_SLOW_FACTOR if slow_until > now else 1)
    remaining = (
        (elapsed - slow_elapsed + slow_elapsed * ATTACK_SLOW_FACTOR)
        * speed
        * (1 if route else min(1, math.hypot(*unit.get("motion_axis", [0, 0]))))
    )
    solids = obstacles(preset)
    while remaining > 1e-9:
        start = unit["position"]
        axis = (
            [route[0][i] - start[i] for i in range(2)]
            if route
            else unit.get("motion_axis", [0, 0])
        )
        length = math.hypot(*axis)
        if length < 1e-9:
            if route:
                route.pop(0)
                continue
            break
        step = min(0.1, remaining, length if route else remaining)
        destination = [start[i] + axis[i] / length * step for i in range(2)]
        if fits(preset, destination, solids):
            unit["position"] = destination
        elif not route:
            # Slide along a wall, while keeping the same total distance budget.
            for candidate in ([destination[0], start[1]], [start[0], destination[1]]):
                if fits(preset, candidate, solids):
                    unit["position"] = candidate
                    break
        else:
            unit["route"] = []
            break
        remaining -= step
        if route and length <= step + 1e-8:
            unit["position"] = route.pop(0)
        if route == [] and unit.get("motion_axis") == [0, 0]:
            break


def stop(unit, now):
    unit.update(motion_axis=[0, 0], motion_until=now, motion_at=now, route=[])


def advance_player(party, key, actor, preset, now):
    from . import tactics

    unit = party["battle"]["players"][key]
    if not unit.get("free_motion"):
        return False
    advance(unit, preset, actor, now)
    if unit.get("hidden"):
        unit["hidden"] = tactics.can_hide(party, key, retaining=True)
    return True


def attacking(party, player, now, until=None):
    from . import tactics, tutorial

    unit = party["battle"]["players"][player]
    advance(
        unit,
        tactics.PRESETS[party["battle"]["preset"]],
        tutorial.unpack(party["characters"][player]),
        now,
    )
    if unit.get("position_client"):
        position_budget(unit, now)
    unit["attack_slow_until"] = max(
        unit.get("attack_slow_until", 0), until or now + ATTACK_RECOVERY
    )


def agent_move(unit, preset, destination, now, duration, elapsed):
    """Advance a hostile along its path without snapping at cell boundaries."""
    from . import tactics

    point = unit.get("agent_waypoint")
    if point is None or math.dist(unit["position"], point) < 0.001:
        route = tactics.path(preset, unit["position"], destination)
        point = route[0] if route else destination
        unit["agent_waypoint"] = list(point)
    budget = min(MAX_CATCHUP, max(0, elapsed)) / duration
    solids = obstacles(preset)
    while budget > 1e-9:
        source = unit["position"]
        distance = math.dist(source, point)
        if distance < 1e-9:
            route = tactics.path(preset, source, destination)
            point = route[0] if route else destination
            unit["agent_waypoint"] = list(point)
            if math.dist(source, point) < 1e-9:
                break
            continue
        step = min(0.1, budget, distance)
        target = [
            a + (b - a) * step / distance for a, b in zip(source, point, strict=True)
        ]
        if not fits(preset, target, solids):
            unit.pop("agent_waypoint", None)
            break
        unit["position"] = target
        budget -= step
    unit["next_move"] = now


def advance_agents_clock(battle, now):
    if battle.get("continuous_agents"):
        battle["agent_elapsed"] = min(
            MAX_CATCHUP, max(0, now - battle.get("agents_at", now))
        )
        battle["agents_at"] = now
