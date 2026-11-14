import json
import socket
from copy import deepcopy

import pytest

from jeuxRPG.multiplayer.living_world import LivingWorld, WorldSimulation
from jeuxRPG.multiplayer.living_world_catalog import DEFAULT_RULES, build_catalog


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Ce test ne doit effectuer aucun accès réseau")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_month_offline_has_bounded_calendar_and_resumable_work():
    simulation = WorldSimulation(build_catalog())
    state = simulation.create(0)
    target = 30 * 86400
    batches = 0
    while simulation.catching_up(state, target):
        state, count = simulation.advance(state, target)
        assert 0 < count <= 128
        assert (
            len(state["queue"]) <= len(state["towns"]) * 3 + len(state["patrols"]) + 1
        )
        assert len(state["events"]) <= 40
        batches += 1
    assert batches > 1
    assert state["processed"] > 1000
    assert simulation.advance(json.loads(json.dumps(state)), target)[1] == 0


def test_town_stalls_never_occupy_an_exit_tile():
    from jeuxRPG.multiplayer import world

    catalog = build_catalog()
    for town in catalog["towns"]:
        definition = world.WORLD_MAP_DATA[town]
        x, y = catalog["maps"][town]["route"][0]
        assert 0 < x < definition["width"] - 1
        assert 0 < y < definition["height"] - 1
        assert [x, y] not in [gate["position"] for gate in definition.get("exits", [])]


@pytest.fixture
def catalog():
    maps = {
        "a": {
            "id": "a",
            "display_id": "field_a",
            "name": "Ville A",
            "zone": "za",
            "town": True,
            "route": [[1, 1], [2, 1], [3, 1], [4, 1]],
        },
        "b": {
            "id": "b",
            "display_id": "field_b",
            "name": "Ville B",
            "zone": "zb",
            "town": True,
            "route": [[1, 1], [1, 2], [1, 3]],
        },
        "woods": {
            "id": "woods",
            "display_id": "field_woods",
            "name": "Bois",
            "zone": "za",
            "town": False,
            "route": [[2, 1], [3, 1], [4, 1]],
        },
    }
    return {
        "version": 1,
        "seed": "test-world",
        "speed": 1,
        "rules": {
            **DEFAULT_RULES,
            "economy_period": 10,
            "patrol_period": 15,
            "raid_period": 50,
            "raid_warning": 5,
            "raid_duration": 10,
            "merchant_stay": 20,
            "npc_cycle": 120,
        },
        "maps": maps,
        "towns": {
            key: {"id": key, "name": maps[key]["name"], "zone": maps[key]["zone"]}
            for key in ("a", "b")
        },
        "journeys": {
            "a": {"b": {"duration": 5, "points": ["a", "b"]}},
            "b": {"a": {"duration": 5, "points": ["b", "a"]}},
        },
        "neighbours": {"a": ["woods"], "woods": ["a", "b"], "b": ["woods"]},
        "goods": {"wood": {"name": "Bois", "buy": 3, "sell": 1}},
    }


def finish(simulation, state, target, budget=128):
    while True:
        state, count = simulation.advance(state, target, budget)
        if not count:
            return state


def canonical(state):
    result = deepcopy(state)
    result["queue"].sort()
    return result


def test_catchup_matches_continuous_simulation_across_multiple_restarts(catalog):
    simulation = WorldSimulation(catalog)
    continuous = simulation.create(0)
    for target in range(1, 1001):
        continuous, _ = simulation.advance(continuous, target)
        if target % 79 == 0:
            continuous = json.loads(json.dumps(continuous))
    resumed = finish(
        simulation, json.loads(json.dumps(simulation.create(0))), 1000, budget=3
    )
    assert canonical(resumed) == canonical(continuous)
    assert len(resumed["events"]) <= catalog["rules"]["history_limit"]
    assert len({event["id"] for event in resumed["events"]}) == len(resumed["events"])
    assert len(resumed["queue"]) <= 20


def test_repeated_deadline_does_not_repeat_attacks_or_economic_effects(catalog):
    simulation = WorldSimulation(catalog)
    state = finish(simulation, simulation.create(0), 200)
    again, count = simulation.advance(state, 200)
    assert count == 0 and again == state
    backwards, count = simulation.advance(state, 100)
    assert count == 0 and backwards == state


def test_catchup_is_bounded_and_does_not_claim_the_future(catalog):
    simulation = WorldSimulation(catalog)
    state, count = simulation.advance(simulation.create(0), 100000, budget=2)
    assert count == 2
    assert state["processed"] == 2
    view = simulation.view(state, 100000, "a")
    assert view["catching_up"] and view["time"] < 100000
    assert view["time"] >= state["time"]


def test_city_attack_damage_resources_and_reconstruction_are_persistent(catalog):
    simulation = WorldSimulation(catalog)
    warning = finish(simulation, simulation.create(0), 50)
    assert warning["towns"]["a"]["raid"]["phase"] == "warning"
    siege = finish(simulation, warning, 55)
    assert siege["towns"]["a"]["raid"]["phase"] == "siege"
    assert any(
        actor["kind"] == "raiders"
        for actor in simulation.view(siege, 58, "a")["nearby"]
    )
    ended = finish(simulation, siege, 65)
    town = ended["towns"]["a"]
    assert town["raid"] is None and town["integrity"] < 100 and town["losses"] == 1
    recovered = finish(simulation, json.loads(json.dumps(ended)), 70)
    assert recovered["towns"]["a"]["integrity"] > town["integrity"]
    for value in recovered["towns"].values():
        assert all(0 <= value[key] <= 500 for key in ("food", "wood", "stone", "gold"))


def test_defenders_change_attack_outcome_deterministically(catalog):
    simulation = WorldSimulation(catalog)
    state = finish(simulation, simulation.create(0), 55)
    state["towns"]["a"]["raid"]["support"] = 100
    state = finish(simulation, state, 65)
    assert state["towns"]["a"]["integrity"] == 100
    assert state["towns"]["a"]["losses"] == 0


def test_caravan_waits_out_a_siege_and_arrives_exactly_once(catalog):
    catalog["rules"]["merchant_stay"] = 50
    simulation = WorldSimulation(catalog)
    state = finish(simulation, simulation.create(0), 55)
    assert state["merchant"]["phase"] == "waiting"
    assert state["merchant"]["visits"] == 0
    state = finish(simulation, json.loads(json.dumps(state)), 66)
    assert state["merchant"]["phase"] == "stationed"
    assert state["merchant"]["town"] == "b" and state["merchant"]["visits"] == 1
    same, count = simulation.advance(state, 66)
    assert count == 0 and same == state


def test_active_positions_move_without_changing_the_dormant_simulation(catalog):
    simulation = WorldSimulation(catalog)
    state = simulation.create(0)
    before = canonical(state)
    first = simulation.view(state, 0, "a")
    later = simulation.view(state, 3, "a")
    assert first["nearby"] and first["nearby"] != later["nearby"]
    assert simulation.view(state, 3)["nearby"] == []
    assert canonical(state) == before
    assert any(actor["kind"] == "resident" for actor in first["nearby"])
    assert any(actor["kind"] == "merchant" for actor in first["nearby"])


def test_builder_catalogue_uses_only_authored_maps_and_traversable_paths():
    from jeuxRPG.multiplayer import tactics, world

    catalog = build_catalog()
    assert catalog["towns"]
    for key, definition in catalog["maps"].items():
        assert key in world.WORLD_MAP_DATA
        assert all(
            tactics.walkable(world.WORLD_MAP_DATA[key], point)
            for point in definition["route"]
        )
    for source, destinations in catalog["journeys"].items():
        for destination, route in destinations.items():
            assert world.path(source, destination, set(world.PLACES)) is not None
            assert route["duration"] > 0


def test_corrupted_or_changed_catalogue_is_not_silently_reset(catalog):
    simulation = WorldSimulation(catalog)
    state = simulation.create(0)
    different = deepcopy(catalog)
    different["seed"] = "changed"
    with pytest.raises(ValueError, match="migration"):
        WorldSimulation(different).advance(state, 100)
    state["queue"].append(deepcopy(state["queue"][0]))
    with pytest.raises(ValueError, match="double"):
        simulation.advance(state, 100)


def test_persistent_calendar_is_atomic_and_recovers_after_transaction_rollback(
    catalog, tmp_path
):
    import sqlite3

    db = sqlite3.connect(tmp_path / "world.sqlite3", isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)")
    world = LivingWorld(db, catalog)
    db.execute("BEGIN")
    world.advance(1, 0)
    db.commit()
    before = db.execute("SELECT value FROM meta").fetchone()[0]
    db.execute("BEGIN")
    world.advance(1, 100)
    db.rollback()
    assert db.execute("SELECT value FROM meta").fetchone()[0] == before
    assert world.load(1, 100)["processed"] == 0
    db.execute("BEGIN")
    final = world.advance(1, 100)
    db.commit()
    db.close()
    db = sqlite3.connect(tmp_path / "world.sqlite3", isolation_level=None)
    db.row_factory = sqlite3.Row
    assert LivingWorld(db, catalog).load(1, 100) == final
    db.close()
