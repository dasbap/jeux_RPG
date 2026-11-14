"""Persistent friendly squads, attached to one tactical encounter at a time.

The world owns the squad; an adventure borrows it for a simulation step. Players
cannot duplicate the soldiers by opening another session or refreshing a view.
"""

from copy import deepcopy

SIZE = 3
MAX_HP = 45
LOW_HP = 0.30
READY_HP = 0.80
DETECTION = 6
LEASH = 12
COHESION = 4
STEP = 0.6  # game seconds; tactical movement retains its own cooldown
LEASE = 15
OFFSCREEN_RECOVERY = 180


def health(member):
    return member["character"]["stats"]["hp"]


def create(identifier, definition, preset, now):
    from . import progression, tactics, tutorial

    route = definition["route"]
    rally = route[len(route) // 2]
    members = {}
    occupied = []
    for index in range(SIZE):
        key = f"{identifier}:soldier:{index}"
        actor = tutorial.create_character(
            {
                "id": key,
                "name": f"Garde {index + 1} · {definition['name']}",
                "class_name": "Knight",
            }
        )
        actor.hp.value = MAX_HP
        actor.hp.current_value = MAX_HP
        home = tactics.free_position(preset, [rally[0] + index - 1, rally[1]], occupied)
        occupied.append(home)
        members[key] = {
            "id": key,
            "character": tutorial.pack(actor),
            "position": home[:],
            "home": home,
            "hidden": False,
            "route": [],
            "next_move": now,
            "next_attack": now,
            "effect_at": now + progression.ACTION_SECONDS * progression.RATIO,
        }
    return {
        "mode": "patrol",
        "owner": None,
        "lease_until": 0,
        "next_step": now,
        "next_heal": now,
        "fallback_at": now + OFFSCREEN_RECOVERY,
        "route_index": 0,
        "direction": 1,
        "rally": list(rally),
        "origin": list(rally),
        "members": members,
    }


def _reset(squad, now):
    for member in squad["members"].values():
        member["character"]["stats"]["hp"]["current"] = health(member)["max"]
        member["character"]["effects"] = []
        member.update(
            position=member["home"][:], route=[], next_attack=now + 3, next_move=now
        )
    squad.update(mode="patrol", owner=None, lease_until=0, next_step=now, target=None)


def settle_offscreen(group, now):
    """Bounded deterministic recovery in an unobserved zone; never replay hits."""
    squad = group.get("squad")
    if (
        not squad
        or squad["mode"] == "patrol"
        or squad.get("lease_until", 0) > now
        or squad.get("fallback_at", now + 1) > now
    ):
        return False
    _reset(squad, now)
    return True


def public_members(group, display_id):
    squad = group.get("squad")
    if not squad:
        return []
    modes = {
        "patrol": "patrouille",
        "combat": "combat contre les monstres hostiles",
        "retreat": "repli collectif",
        "recover": "soins au point de ralliement",
        "down": "hors combat · renforts attendus",
    }
    return [
        {
            "id": member["id"],
            "kind": "guards",
            "name": member["character"]["name"],
            "activity": modes[squad["mode"]],
            "mode": squad["mode"],
            "position": member["position"][:],
            "map": display_id,
            "hp": health(member)["current"],
            "max_hp": health(member)["max"],
        }
        for member in squad["members"].values()
    ]


def _low(actors):
    return any(
        actor.hp.current_value <= actor.hp.value * LOW_HP for actor in actors.values()
    )


def react(squad, actors, now, messages):
    if not actors:
        return
    if not any(actor.is_alive() for actor in actors.values()):
        if squad["mode"] != "down":
            squad.update(mode="down", fallback_at=now + OFFSCREEN_RECOVERY)
            messages.append(
                "La patrouille est hors combat ; des renforts sont attendus au village."
            )
        return
    if squad["mode"] in ("patrol", "combat") and _low(actors):
        squad.update(mode="retreat", target=None, fallback_at=now + OFFSCREEN_RECOVERY)
        for member in squad["members"].values():
            member["route"] = []
        messages.append(
            "Un garde est grièvement blessé : toute la patrouille se replie vers son point de ralliement."
        )


def _visible_hostiles(party, squad, preset, actors):
    from . import mob_rules, tactics

    result = []
    for mob in party["mobs"]:
        if not mob_rules.is_hostile(mob) or mob["stats"]["hp"]["current"] <= 0:
            continue
        distances = [
            tactics.distance(member["position"], mob["position"])
            for key, member in squad["members"].items()
            if actors[key].is_alive()
            and tactics.sight(preset, member["position"], mob["position"])
        ]
        if distances and min(distances) <= DETECTION:
            result.append((min(distances), mob["combat_id"], mob))
    result.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in result]


def has_threat(party, squad, preset):
    from . import mob_rules, tactics

    return any(
        mob_rules.is_hostile(mob)
        and mob["stats"]["hp"]["current"] > 0
        and any(
            health(member)["current"] > 0
            and tactics.distance(member["position"], mob["position"]) <= DETECTION
            and tactics.sight(preset, member["position"], mob["position"])
            for member in squad["members"].values()
        )
        for mob in party["mobs"]
    )


def _move(member, destination, squad, actors, preset, now, retreat=False):
    from . import tactics

    actor = actors[member["id"]]
    if (
        member["next_move"] > now
        or actor.is_stunned()
        or (not actor.is_alive() and not retreat)
    ):
        return
    route = tactics.path(preset, member["position"], destination)
    if not route:
        return
    candidate = route[0]
    others = [other for key, other in squad["members"].items() if key != member["id"]]
    if any(other["position"] == candidate for other in others):
        blocked = {
            **preset,
            "blocked": [
                *preset.get("blocked", []),
                *(other["position"] for other in others),
            ],
        }
        alternative = tactics.path(blocked, member["position"], destination)
        if not alternative:
            return
        candidate = alternative[0]
    if retreat:
        current = max(
            (
                tactics.distance(member["position"], other["position"])
                for other in others
            ),
            default=0,
        )
        spread = max(
            (tactics.distance(candidate, other["position"]) for other in others),
            default=0,
        )
        if spread > COHESION and spread >= current:
            return
    member["next_move"] = now + tactics.step_time(
        member["position"], candidate, tactics.MOVE_TIME
    )
    member["position"] = candidate


def _guard_kill(party, mob, players, now, random, messages):
    from . import tactics, tutorial

    if tactics.advance_boss_phase(mob, messages):
        return
    party["mobs"].remove(mob)
    party["characters"] = {
        key: tutorial.pack(players[key]) for key in party["characters"]
    }
    tactics.defeated(
        party, mob, now, random, messages, credited=mob.get("player_assisted", False)
    )
    for key in party["characters"]:
        players[key] = tutorial.unpack(party["characters"][key])
    party["autosave_checkpoint"] = party.get("autosave_checkpoint", 0) + 1
    tutorial.sync_mobs(party)


def _fight(party, squad, actors, players, enemies, preset, now, random, messages):
    from . import tactics, tutorial

    if not enemies:
        squad.update(mode="patrol", target=None)
        return
    if squad["mode"] != "combat":
        leader = next(
            member for key, member in squad["members"].items() if actors[key].is_alive()
        )
        squad["origin"] = leader["position"][:]
    squad["mode"] = "combat"
    target = enemies[0]
    if tactics.distance(target["position"], squad["origin"]) > LEASH:
        squad.update(mode="retreat", target=None)
        return
    squad["target"] = target["combat_id"]
    for key, member in squad["members"].items():
        actor = actors[key]
        if not actor.is_alive() or actor.is_stunned():
            continue
        if target not in party["mobs"]:
            break
        distance = tactics.distance(member["position"], target["position"])
        if distance <= tactics.AI_RULES["melee_range"] and tactics.sight(
            preset, member["position"], target["position"]
        ):
            if member["next_attack"] > now:
                continue
            enemy = tutorial.unpack(target)
            enemy.drop_xp = lambda killer: ""
            before = enemy.hp.current_value
            enemy.lose_hp(actor, 5)
            target.update(tutorial.pack(enemy))
            tactics.damaged(party, target, key, now)
            member["next_attack"] = now + 3
            messages.append(
                f"{actor.name} attaque {target['name']} : {max(0, before - enemy.hp.current_value)} dégâts."
            )
            if not enemy.is_alive():
                _guard_kill(party, target, players, now, random, messages)
        else:
            _move(member, target["position"], squad, actors, preset, now)


def _withdraw(squad, actors, enemies, preset, now, messages):
    from . import tactics

    members = list(squad["members"].values())
    if squad["mode"] == "retreat":
        weakest = min(
            members,
            key=lambda member: (
                actors[member["id"]].hp.current_value
                / max(1, actors[member["id"]].hp.value)
            ),
        )
        # Those nearest the rally point clear the way for the wounded.
        for member in sorted(
            members, key=lambda unit: tactics.distance(unit["position"], unit["home"])
        ):
            destination = (
                weakest["position"]
                if tactics.distance(member["position"], weakest["position"])
                > COHESION - 1
                else member["home"]
            )
            _move(member, destination, squad, actors, preset, now, retreat=True)
        if all(
            tactics.distance(member["position"], member["home"]) <= 1.5
            for member in members
        ):
            squad.update(mode="recover", next_heal=now + 3)
            messages.append(
                "La patrouille est regroupée au point de ralliement et soigne ses blessés."
            )
    if squad["mode"] == "recover" and not enemies and squad["next_heal"] <= now:
        for actor in actors.values():
            actor.hp.current_value = min(actor.hp.value, actor.hp.current_value + 3)
        squad["next_heal"] = now + 3
        if all(
            actor.hp.current_value >= actor.hp.value * READY_HP
            for actor in actors.values()
        ):
            squad.update(mode="patrol", target=None)
            messages.append(
                "Les gardes ont récupéré ; la patrouille reprend son service."
            )


def _patrol(squad, definition, actors, preset, now):
    from . import tactics

    route = definition["route"]
    index = min(squad["route_index"], len(route) - 1)
    leader = next(iter(squad["members"].values()))
    if tactics.distance(leader["position"], route[index]) <= 1 and len(route) > 1:
        if index in (0, len(route) - 1):
            squad["direction"] = 1 if index == 0 else -1
        index += squad["direction"]
        squad["route_index"] = index
    occupied = []
    for offset, member in enumerate(squad["members"].values()):
        point = tactics.free_position(
            preset, [route[index][0] + offset - 1, route[index][1]], occupied
        )
        occupied.append(point)
        _move(member, point, squad, actors, preset, now)


def prepare(party, players, preset, now, random, messages):
    """Run soldiers before hostile AI, then expose them as normal enemy targets."""
    from . import progression, tutorial

    squad = party["battle"].get("guard_patrol")
    if not squad:
        return {}, {}
    actors = {
        key: tutorial.unpack(member["character"])
        for key, member in squad["members"].items()
    }
    for key, actor in actors.items():
        actor.drop_xp = lambda killer: ""
        member = squad["members"][key]
        if actor.status["alteration"] and member["effect_at"] <= now:
            actor._update_status()
            member["effect_at"] = now + progression.ACTION_SECONDS * progression.RATIO
    react(squad, actors, now, messages)
    if squad["mode"] == "down" and now >= squad["fallback_at"]:
        _reset(squad, now)
        actors = {
            key: tutorial.unpack(member["character"])
            for key, member in squad["members"].items()
        }
        for actor in actors.values():
            actor.drop_xp = lambda killer: ""
    if squad["next_step"] <= now:
        squad["next_step"] = now + STEP
        enemies = _visible_hostiles(party, squad, preset, actors)
        if squad["mode"] in ("retreat", "recover"):
            _withdraw(squad, actors, enemies, preset, now, messages)
        elif squad["mode"] != "down":
            _fight(
                party, squad, actors, players, enemies, preset, now, random, messages
            )
            if squad["mode"] == "patrol":
                _patrol(squad, squad["route_definition"], actors, preset, now)
    return actors, squad["members"]


def finish(party, squad, actors, now, messages):
    from .tutorial import pack

    if not actors:
        return
    react(squad, actors, now, messages)
    for key, actor in actors.items():
        member = squad["members"][key]
        actor.hp.current_value = max(0, min(actor.hp.value, actor.hp.current_value))
        member["character"] = pack(actor)
        member["effect_at"] = party.get("effect_at", {}).pop(key, member["effect_at"])


def attach(service, party, session_id, now):
    """Claim one shared patrol; another adventure may observe but never double-tick it."""
    from . import fields

    life = service.world_life
    map_id = party.get("field_map")
    if life is None or not map_id or not party.get("battle"):
        return None
    first = next(iter(party["characters"]), None)
    realm = service.runtime_presence.get(first, {}).get("realm", 1)
    state = deepcopy(life.advance(realm, now))
    simulation = life.simulation
    if simulation.catching_up(state, now * life.speed):
        return None
    group_key = next(
        (
            key
            for key, group in sorted(state["patrols"].items())
            if group["kind"] == "guards" and group["map"] == map_id
        ),
        None,
    )
    if not group_key:
        return None
    before = deepcopy(state)
    group = state["patrols"][group_key]
    squad = (
        group.setdefault(
            "squad",
            create(
                group_key, simulation.catalog["maps"][map_id], fields.MAPS[map_id], now
            ),
        )
        if "squad" not in group
        else group["squad"]
    )
    owner = squad.get("owner")
    if owner and owner != session_id and squad.get("lease_until", 0) > now:
        return None
    squad.update(owner=session_id, lease_until=now + LEASE)
    # Geometry is ephemeral; it must not be copied into every world checkpoint.
    squad["route_definition"] = {"route": simulation.catalog["maps"][map_id]["route"]}
    party["battle"]["guard_patrol"] = squad
    return {
        "state": state,
        "before": before,
        "realm": realm,
        "key": group_key,
        "squad": squad,
        "map": map_id,
        "claimed": has_threat(party, squad, fields.MAPS[map_id]),
    }


def commit(service, party, context, session_id, now):
    if context is None:
        return
    squad = context["squad"]
    squad.pop("route_definition", None)
    for snapshot in [party, *party.get("fields", {}).values()]:
        if snapshot.get("battle"):
            snapshot["battle"].pop("guard_patrol", None)
    if party.get("field_map") != context["map"] or (
        squad["mode"] == "patrol" and not context["claimed"]
    ):
        squad.update(owner=None, lease_until=0)
    else:
        squad.update(owner=session_id, lease_until=now + LEASE)
    if squad["mode"] != "patrol":
        squad["fallback_at"] = (
            max(squad["fallback_at"], now + OFFSCREEN_RECOVERY)
            if squad["mode"] != "down"
            else squad["fallback_at"]
        )
    if context["state"] != context["before"]:
        if squad["mode"] != "patrol":
            party["autosave_checkpoint"] = party.get("autosave_checkpoint", 0) + 1
        service.world_life.save(context["realm"], context["state"])
