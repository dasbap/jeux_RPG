import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_guard_patrols import arena  # noqa: F401
from test_living_world import no_network  # noqa: F401
from world_checks import assert_connected_world

from jeuxRPG.multiplayer import fields, guard_patrols, tactics, world
from jeuxRPG.multiplayer.living_world import LivingWorld, WorldSimulation
from jeuxRPG.multiplayer.living_world_catalog import build_catalog
from jeuxRPG.multiplayer.map_playability import issues
from jeuxRPG.multiplayer.world_topology import compile_world

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def expanded(monkeypatch):
    maps = json.loads(
        (ROOT / "projects/authored/world.json").read_text(encoding="utf8")
    )
    compiled = compile_world(maps)
    for name, value in zip(
        (
            "PLACES",
            "VILLAGE_STREETS",
            "ROUTES",
            "LEVELS",
            "POINT_MAPS",
            "ZONE_ENTRIES",
            "EDGES",
        ),
        compiled,
        strict=True,
    ):
        monkeypatch.setattr(world, name, value)
    monkeypatch.setattr(world, "WORLD_MAP_DATA", maps)
    monkeypatch.setattr(fields, "MAPS", maps)
    return maps, build_catalog()


def test_city_districts_forest_and_mountains_are_reachable_and_separate(expanded):
    maps, catalog = expanded
    assert_connected_world(maps)
    assert set(catalog["maps"]) == set(maps)
    assert maps["rosee"]["width"] > 64 and maps["rosee"]["height"] > 40
    assert not issues(maps)
    for target in (
        "rosee_dortoir",
        "rosee_armurerie",
        "rosee_remparts",
        "rosee_ruisseau",
        "rosee_col",
        "rosee_tour",
        "lisiere",
        "brume",
        "clearing",
    ):
        assert world.path("rosee", target, set(world.PLACES)) is not None
    assert catalog["maps"]["rosee"]["zone"] == "zone_rosee"
    assert catalog["maps"]["forest"]["zone"] == "forets_rosee"
    assert catalog["maps"]["rosee_carriere"]["zone"] == "monts_rosee"
    assert {"rosee", "brume"} <= set(catalog["towns"])
    assert all(
        item["position"] in maps["rosee"]["cover"]
        for item in maps["rosee"]["decorations"]
        if item["kind"] == "wall"
    )
    assert any(item["kind"] == "bed" for item in maps["rosee_dortoir"]["decorations"])


def test_geography_migration_preserves_economy_raid_and_calendar(expanded):
    _, catalog = expanded
    simulation = WorldSimulation(catalog)
    state = simulation.create(0)
    state, _ = simulation.advance(state, 7200)
    state["towns"]["rosee"].update(food=17, gold=23, integrity=61)
    state["catalog"] = catalog["previous_catalogs"][0]
    state["patrols"].pop("guards:rosee_caserne")
    state["queue"] = [e for e in state["queue"] if e[3] != "guards:rosee_caserne"]
    before = deepcopy(state)
    migrated = simulation.migrate_catalog(state)
    assert state == before
    assert migrated["towns"] == before["towns"]
    assert migrated["merchant"] == before["merchant"]
    assert migrated["events"] == before["events"]
    assert migrated["time"] == before["time"]
    assert migrated["processed"] == before["processed"]
    assert "guards:rosee_caserne" in migrated["patrols"]
    assert simulation.migrate_catalog(migrated) is migrated
    assert len({event[1] for event in migrated["queue"]}) == len(migrated["queue"])
    state["catalog"] = "unknown-catalog"
    with pytest.raises(ValueError):
        simulation.migrate_catalog(state)


def test_each_district_retains_its_garrison_even_before_any_player_visits(expanded):
    _, catalog = expanded
    simulation = WorldSimulation(catalog)
    state = simulation.create(0)
    expected = {
        key: group["map"]
        for key, group in state["patrols"].items()
        if catalog["maps"][group["map"]].get("garrison")
    }
    for instant in range(900, 9001, 900):
        state, _ = simulation.advance(state, instant)
        assert {key: state["patrols"][key]["map"] for key in expected} == expected


def test_district_guards_share_the_village_raid_and_migration_is_persisted(expanded):
    maps, catalog = expanded
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)")
    life = LivingWorld(db, catalog)
    service = SimpleNamespace(world_life=life, runtime_presence={})
    try:
        db.execute("BEGIN")
        with db:
            state = life.simulation.create(0)
            state["catalog"] = catalog["previous_catalogs"][0]
            state["towns"]["rosee"]["raid"] = {"phase": "siege"}
            life.save(1, state)
            party = {
                "field_map": "rosee_caserne",
                "battle": {},
                "characters": {"p0": {}},
                "mobs": [],
            }
            # Tactical battles always contain a preset.
            party["battle"]["preset"] = maps["rosee_caserne"]["id"]
            context = guard_patrols.attach(service, party, "test", 0)
            assert context["squad"]["defending_raid"]
            assert {m["role"] for m in context["squad"]["members"].values()} == {
                "knight",
                "archer",
            }
            guard_patrols.commit(service, party, context, "test", 0)
            stored = json.loads(
                db.execute(
                    "SELECT value FROM meta WHERE key='world_life:1'"
                ).fetchone()[0]
            )
            assert stored["catalog"] == life.simulation.identity
            assert stored["towns"]["rosee"]["raid"]["phase"] == "siege"
    finally:
        db.close()


def test_archer_shoots_at_range_while_knights_must_approach(arena):  # noqa: F811
    from jeuxRPG.multiplayer import tutorial

    data, squad, preset = arena
    data["mobs"][0]["position"] = [10, 6]
    positions = {key: member["position"][:] for key, member in squad["members"].items()}
    actors = {key: tutorial.unpack(value) for key, value in data["characters"].items()}
    messages = []
    guard_patrols.prepare(data, actors, preset, 0, lambda: 0.5, messages)
    assert data["mobs"][0]["stats"]["hp"]["current"] < 100
    assert len([message for message in messages if "attaque" in message]) == 1
    for key, member in squad["members"].items():
        assert (member["position"] == positions[key]) == (member["role"] == "archer")
    assert any("archer" in message for message in messages)


def test_saved_guards_are_relocated_when_a_new_wall_occupies_their_position(arena):  # noqa: F811
    _, squad, preset = arena
    first = next(iter(squad["members"].values()))
    guard_patrols.health(first)["current"] = 11
    preset["cover"] = [first["position"][:], first["home"][:]]
    guard_patrols._repair_positions(squad, preset)
    assert tactics.walkable(preset, first["position"])
    assert tactics.walkable(preset, first["home"])
    assert guard_patrols.health(first)["current"] == 11
