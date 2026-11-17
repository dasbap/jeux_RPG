import json
from copy import deepcopy

import pytest
from test_living_world import no_network  # noqa: F401
from test_living_world_service import Clock, game, party_of, prepare  # noqa: F401
from test_single_runtime import d1  # noqa: F401
from test_tactics import party

from jeuxRPG.multiplayer import fields, guard_patrols, tactics


@pytest.fixture
def arena(monkeypatch):
    data = party()
    preset = {
        "id": "guard_arena",
        "name": "Village test",
        "width": 28,
        "height": 18,
        "cover": [],
        "blocked": [],
        "water": [],
        "paths": [],
        "exits": [],
        "sites": [],
    }
    monkeypatch.setitem(tactics.PRESETS, "guard_arena", preset)
    data["battle"]["preset"] = "guard_arena"
    data["battle"]["next_brain"] = 0
    data["battle"]["players"]["p0"]["position"] = [25, 14]
    definition = {"name": "Village test", "route": [[3, 5], [3, 6], [3, 7], [4, 7]]}
    squad = guard_patrols.create("guards:test", definition, preset, 0)
    squad["route_definition"] = {"route": definition["route"]}
    for index, member in enumerate(squad["members"].values()):
        member["position"] = [[5, 5], [5, 6], [6, 5]][index]
        member["home"] = [3, 5 + index]
    mob = data["mobs"][0]
    mob.update(
        position=[6, 6],
        hostile=True,
        next_attack=10000,
        next_move=10000,
        calling_until=None,
        needs_call=False,
        state="chase",
        target=None,
    )
    mob["stats"]["hp"] = {"max": 100, "current": 100}
    mob["stats"]["endurance"] = {"max": 0, "current": 0}
    data["battle"]["guard_patrol"] = squad
    return data, squad, preset


def test_guards_attack_nearby_hostiles_without_player_orders(arena):
    data, squad, _ = arena
    before = data["mobs"][0]["stats"]["hp"]["current"]
    messages = tactics.advance(data, 0, lambda: 0.5)
    assert data["mobs"][0]["stats"]["hp"]["current"] < before
    assert squad["mode"] == "combat"
    assert any("Garde" in message and "attaque" in message for message in messages)
    assert set(data["characters"]) == {"p0"}


def test_neutral_mobs_and_monsters_behind_cover_are_not_attacked(arena):
    data, squad, preset = arena
    mob = data["mobs"][0]
    mob["hostile"] = False
    tactics.advance(data, 0, lambda: 0.5)
    assert mob["stats"]["hp"]["current"] == 100
    assert squad["mode"] == "patrol"
    mob["hostile"] = True
    mob["position"] = [12, 6]
    preset["cover"] = [[9, y] for y in range(18)]
    before = mob["stats"]["hp"]["current"]
    tactics.advance(data, 1, lambda: 0.5)
    assert mob["stats"]["hp"]["current"] == before


def test_monsters_retaliate_against_guards_and_do_not_hurt_player_achievements(arena):
    data, squad, _ = arena
    for member in squad["members"].values():
        member["next_attack"] = 10000
    first = next(iter(squad["members"]))
    mob = data["mobs"][0]
    mob.update(
        target=first, windup_until=0, next_attack=0, attack_damage=20, needs_call=False
    )
    player = deepcopy(data["characters"]["p0"])
    tactics.advance(data, 0, lambda: 0.5)
    assert (
        min(
            guard_patrols.health(member)["current"]
            for member in squad["members"].values()
        )
        < 45
    )
    assert data["characters"]["p0"]["stats"]["hp"] == player["stats"]["hp"]
    assert not data["battle"]["damage_received"]


def test_one_wounded_guard_triggers_group_retreat_and_stops_all_attacks(arena):
    data, squad, _ = arena
    next(iter(squad["members"].values()))["character"]["stats"]["hp"]["current"] = 13
    before = data["mobs"][0]["stats"]["hp"]["current"]
    messages = tactics.advance(data, 0, lambda: 0.5)
    assert squad["mode"] == "retreat"
    assert data["mobs"][0]["stats"]["hp"]["current"] == before
    assert any("toute la patrouille se replie" in message for message in messages)
    for step in range(1, 35):
        tactics.advance(data, step * 0.6, lambda: 0.5)
        members = list(squad["members"].values())
        assert (
            max(
                tactics.distance(a["position"], b["position"])
                for a in members
                for b in members
            )
            <= guard_patrols.COHESION
        )
    assert squad["mode"] == "recover"


def test_regrouped_guards_heal_and_wait_until_every_soldier_is_ready(arena):
    data, squad, _ = arena
    data["mobs"] = []
    for member in squad["members"].values():
        member["position"] = member["home"][:]
    next(iter(squad["members"].values()))["character"]["stats"]["hp"]["current"] = 13
    squad["mode"] = "retreat"
    tactics.advance(data, 0, lambda: 0.5)
    assert squad["mode"] == "recover"
    for instant in range(3, 24, 3):
        tactics.advance(data, instant, lambda: 0.5)
        assert squad["mode"] == "recover"
    tactics.advance(data, 24, lambda: 0.5)
    assert squad["mode"] == "patrol"
    assert (
        min(
            guard_patrols.health(member)["current"]
            for member in squad["members"].values()
        )
        >= 36
    )


@pytest.mark.parametrize("assisted", [False, True])
def test_guard_kills_only_reward_players_who_participated(arena, assisted):
    data, squad, _ = arena
    mob = data["mobs"][0]
    mob["stats"]["hp"]["current"] = 1
    mob["player_assisted"] = assisted
    before = data["characters"]["p0"]["exp"]
    tactics.advance(data, 0, lambda: 0.5)
    assert not data["mobs"]
    if assisted:
        assert data["characters"]["p0"]["exp"] > before
    else:
        assert data["characters"]["p0"]["exp"] == before
        assert data["battle"]["corpses"][-1]["loot"] == {}


def town_party(game, name="Alice"):  # noqa: F811
    player, session, town = prepare(game, name)
    data = party_of(game, session)
    anchor = game.world_life.simulation.catalog["maps"][town]["route"][
        len(game.world_life.simulation.catalog["maps"][town]["route"]) // 2
    ]
    fields.enter(data, town, anchor, 0)
    data["mobs"] = []
    data["mob"] = None
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(data), session["id"]),
    )
    return player, session, town


def test_shared_guard_state_is_persisted_and_private_context_is_not_saved(game):  # noqa: F811
    player, session, town = town_party(game)
    game.tick()
    state = game.world_life.load(1, 0)
    group = next(
        group
        for group in state["patrols"].values()
        if group["kind"] == "guards" and group["map"] == town
    )
    assert len(group["squad"]["members"]) == 3
    assert "route_definition" not in group["squad"]
    assert "guard_patrol" not in party_of(game, session)["battle"]
    snapshot = game.state(player["token"])["session"]["tutorial"]["living_world"]
    guards = [actor for actor in snapshot["nearby"] if actor["kind"] == "guards"]
    assert all(actor["max_hp"] == 45 for actor in guards)
    assert all("squad" not in patrol for patrol in snapshot["patrols"])


def test_another_session_cannot_double_tick_an_engaged_patrol(game):  # noqa: F811
    _, session, town = town_party(game)
    data = party_of(game, session)
    with game._transaction():
        first = guard_patrols.attach(game, data, session["id"], 0)
        first["squad"]["mode"] = "combat"
        guard_patrols.commit(game, data, first, session["id"], 0)
    _, other, _ = town_party(game, "Bob")
    with game._transaction():
        assert guard_patrols.attach(game, party_of(game, other), other["id"], 0) is None


def test_offscreen_recovery_is_bounded_and_idempotent(arena):
    _, squad, _ = arena
    squad.pop("route_definition", None)
    squad.update(mode="retreat", owner=None, lease_until=0, fallback_at=180)
    first = next(iter(squad["members"].values()))
    first["character"]["stats"]["hp"]["current"] = 5
    group = {"squad": squad}
    assert not guard_patrols.settle_offscreen(group, 179)
    assert guard_patrols.settle_offscreen(group, 180)
    assert first["character"]["stats"]["hp"]["current"] == 45
    assert not guard_patrols.settle_offscreen(group, 180)


@pytest.mark.parametrize("raid", [False, True])
def test_damage_during_a_monster_turn_only_orders_retreat_outside_raids(arena, raid):
    data, squad, _ = arena
    squad["defending_raid"] = raid
    for member in squad["members"].values():
        member["next_attack"] = 10000
    first = next(iter(squad["members"]))
    mob = data["mobs"][0]
    mob.update(
        target=first, windup_until=0, next_attack=0, attack_damage=40, needs_call=False
    )
    tactics.advance(data, 0, lambda: 0.5)
    assert squad["mode"] == ("combat" if raid else "retreat")
    assert (
        min(
            guard_patrols.health(member)["current"]
            for member in squad["members"].values()
        )
        <= 13
    )


def test_guards_do_not_heal_with_hostiles_still_nearby(arena):
    data, squad, _ = arena
    squad.update(mode="recover", next_heal=0)
    first = next(iter(squad["members"].values()))
    first["character"]["stats"]["hp"]["current"] = 13
    for instant in (0, 3, 6, 9):
        tactics.advance(data, instant, lambda: 0.5)
    assert guard_patrols.health(first)["current"] == 13
    assert squad["mode"] == "recover"


def test_same_timestamp_cannot_duplicate_guard_attacks(arena):
    data, _, _ = arena
    tactics.advance(data, 0, lambda: 0.5)
    remaining = data["mobs"][0]["stats"]["hp"]["current"]
    for _ in range(10):
        tactics.advance(data, 0, lambda: 0.5)
    assert data["mobs"][0]["stats"]["hp"]["current"] == remaining


@pytest.mark.parametrize("mode", ["patrol", "retreat", "recover"])
def test_raid_defenders_keep_fighting_even_when_wounded(arena, mode):
    data, squad, _ = arena
    squad.update(defending_raid=True, mode=mode, origin=[25, 17])
    first = next(iter(squad["members"].values()))
    guard_patrols.health(first)["current"] = 5
    tactics.advance(data, 0, lambda: 0.5)
    assert squad["mode"] == "combat"
    assert data["mobs"][0]["stats"]["hp"]["current"] < 100
    assert guard_patrols.health(first)["current"] == 5
    squad["defending_raid"] = False
    tactics.advance(data, 1, lambda: 0.5)
    assert squad["mode"] in ("retreat", "recover")


def test_raid_does_not_make_fallen_guards_keep_fighting(arena):
    data, squad, _ = arena
    squad["defending_raid"] = True
    for member in squad["members"].values():
        guard_patrols.health(member)["current"] = 0
    tactics.advance(data, 0, lambda: 0.5)
    assert squad["mode"] == "down"
    assert data["mobs"][0]["stats"]["hp"]["current"] == 100


@pytest.mark.parametrize(
    "phase, expected", [("warning", False), ("siege", True), (None, False)]
)
def test_only_active_raid_in_the_patrol_village_disables_retreat(game, phase, expected):  # noqa: F811
    _, session, town = town_party(game)
    with game._transaction():
        state = deepcopy(game.world_life.load(1, 0))
        state["towns"][town]["raid"] = {"phase": phase} if phase else None
        game.world_life.save(1, state)
        data = party_of(game, session)
        context = guard_patrols.attach(game, data, session["id"], 0)
        assert context["squad"]["defending_raid"] is expected
        guard_patrols.commit(game, data, context, session["id"], 0)


def test_guards_and_adventure_checkpoint_use_the_same_durable_batch(d1):  # noqa: F811
    from jeuxRPG.multiplayer.realtime_store import RuntimeStore

    store = RuntimeStore(
        {
            "RPG_RUNTIME_MODE": "single",
            "RPG_DATABASE_BACKEND": "d1",
            "RPG_D1_WORKER_URL": "https://isolated.invalid",
            "RPG_D1_SERVICE_TOKEN": "local-test-token-" * 3,
            "RPG_LIVING_WORLD": "1",
        },
        clock=Clock(),
    )
    try:
        store.service.legacy_auth = True
        _, session, town = town_party(store.service)
        store.tick()
        store.saved(store.pending_batch())
        with store.service._transaction():
            state = deepcopy(store.service.world_life.load(1, 0))
            group = next(
                group
                for group in state["patrols"].values()
                if group["kind"] == "guards" and group["map"] == town
            )
            next(iter(group["squad"]["members"].values()))["character"]["stats"]["hp"][
                "current"
            ] = 5
            store.service.world_life.save(1, state)
        store.service.clock.value = 0.6
        store.tick()
        batch = store.pending_batch()
        assert ("meta", ("world_life:1",)) in batch
        assert ("tutorials", (session["id"],)) in batch
        assert (
            "guard_patrol"
            not in json.loads(batch[("tutorials", (session["id"],))]["data"])["battle"]
        )
    finally:
        store.close()


def test_guard_health_is_separate_for_each_realm(game):  # noqa: F811
    player, _, town = town_party(game)
    game.realm_count = 2
    game.runtime_presence[player["player"]["id"]] = {"realm": 2, "seen": 0}
    game.tick()
    first = game.world_life.load(1, 0)
    second = game.world_life.load(2, 0)
    assert not any("squad" in group for group in first["patrols"].values())
    assert any(
        "squad" in group for group in second["patrols"].values() if group["map"] == town
    )
