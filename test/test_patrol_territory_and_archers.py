import json
from copy import deepcopy

import pytest
from test_living_world import catalog, no_network  # noqa: F401
from test_tactics import party

from jeuxRPG.multiplayer import map_building, tactics, tutorial
from jeuxRPG.multiplayer.living_world import LivingWorld, WorldSimulation
from jeuxRPG.multiplayer.living_world_catalog import build_catalog
from jeuxRPG.multiplayer.mob_rules import validate_mobs


def test_patrols_never_mix_friendly_towns_and_monster_territory(catalog):  # noqa: F811
    simulation = WorldSimulation(catalog)
    state = simulation.create(0)
    for target in range(0, 1000, 5):
        state, _ = simulation.advance(state, target)
        for group in state["patrols"].values():
            assert catalog["maps"][group["map"]]["town"] == (group["kind"] == "guards")


def test_saved_guards_in_goblin_camp_are_relocated_without_resetting_the_world(
    tmp_path,
):
    import sqlite3

    connection = sqlite3.connect(tmp_path / "world.sqlite3")
    connection.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)")
    data = build_catalog()
    repository = LivingWorld(connection, data)
    try:
        state = repository.simulation.create(0)
        guards = next(key for key in state["patrols"] if key.startswith("guards:"))
        state["patrols"][guards]["map"] = "hunt"
        town = next(iter(state["towns"]))
        state["towns"][town]["food"] = 37
        connection.execute("BEGIN")
        with connection:
            repository.save(1, state)
        connection.execute("BEGIN")
        with connection:
            fixed = repository.advance(1, 0)
        assert data["maps"][fixed["patrols"][guards]["map"]]["town"]
        assert fixed["towns"][town]["food"] == 37
        assert fixed["queue"] == state["queue"]
        assert fixed["processed"] == 0
        stored = json.loads(
            connection.execute(
                "SELECT value FROM meta WHERE key='world_life:1'"
            ).fetchone()[0]
        )
        assert stored == fixed
        assert not any(
            actor["kind"] == "guards"
            for actor in repository.simulation.view(fixed, 0, "hunt")["nearby"]
        )
        second, count = repository.simulation.advance(fixed, 0)
        assert count == 0 and second == fixed
    finally:
        connection.close()


def intent_fixture(attack_range=6):
    data = party()
    mob = data["mobs"][0]
    mob.update(
        position=[2, 2],
        state="chase",
        target="p0",
        last_known=[7, 2],
        attack_range=attack_range,
        attack_name="Tir de flèche",
        attack_damage=20,
        windup_until=0.1,
        next_attack=0,
        next_move=1000,
    )
    units = data["battle"]["players"]
    units["p0"]["position"] = [7, 2]
    characters = {"p0": tutorial.unpack(data["characters"]["p0"])}
    preset = {"width": 20, "height": 10, "cover": [], "blocked": []}
    return data, mob, units, characters, preset


def resolve_intent(fixture, now=1):
    data, mob, units, characters, preset = fixture
    messages = []
    tactics._resolve_mob_intent(
        data,
        mob,
        characters,
        units,
        preset,
        now,
        lambda: 0.5,
        messages,
        "p0",
        [(5, "p0")],
    )
    return messages


def test_archer_shoots_within_range_without_walking_into_melee():
    fixture = intent_fixture()
    _, mob, _, characters, _ = fixture
    hp = characters["p0"].hp.current_value
    messages = resolve_intent(fixture)
    assert characters["p0"].hp.current_value < hp
    assert mob["position"] == [2, 2]
    assert any("Tir de flèche" in message for message in messages)


@pytest.mark.parametrize("blocked", [False, True])
def test_pending_arrow_cannot_hit_after_target_leaves_range_or_hides(blocked):
    fixture = intent_fixture()
    _, mob, units, characters, preset = fixture
    if blocked:
        preset["cover"] = [[4, 2]]
    else:
        units["p0"]["position"] = [9, 2]
    hp = characters["p0"].hp.current_value
    messages = resolve_intent(fixture)
    assert characters["p0"].hp.current_value == hp
    assert mob["windup_until"] is None
    assert not any("PV perdus" in message for message in messages)


def test_melee_mob_still_cannot_attack_five_tiles_away():
    fixture = intent_fixture(tactics.AI_RULES["melee_range"])
    _, _, _, characters, _ = fixture
    hp = characters["p0"].hp.current_value
    resolve_intent(fixture)
    assert characters["p0"].hp.current_value == hp


def test_archer_windup_and_cooldown_prevent_attacking_each_tick():
    fixture = intent_fixture()
    _, mob, _, characters, _ = fixture
    mob["windup_until"] = None
    hp = characters["p0"].hp.current_value
    resolve_intent(fixture)
    assert characters["p0"].hp.current_value == hp
    deadline = mob["windup_until"]
    assert deadline > 1
    resolve_intent(fixture, deadline)
    after = characters["p0"].hp.current_value
    assert after < hp
    resolve_intent(fixture, deadline + 0.01)
    assert characters["p0"].hp.current_value == after


def test_old_saved_mobs_gain_species_attack_settings_without_losing_hp(monkeypatch):
    mobs = deepcopy(map_building.MOBS)
    mobs["gobelin_archer"] = deepcopy(mobs["goblin"])
    mobs["gobelin_archer"].update(attack_range=6.0, attack_name="Tir de flèche")
    monkeypatch.setattr(map_building, "MOBS", mobs)
    legacy = {
        "mob_id": "gobelin_archer",
        "hostile": True,
        "stats": {"hp": {"current": 5}},
    }
    data = {"mobs": [legacy], "fields": {"hunt": {"mobs": [deepcopy(legacy)]}}}
    map_building.migrate_behavior(data, {})
    for mob in (legacy, data["fields"]["hunt"]["mobs"][0]):
        assert mob["attack_range"] == 6
        assert mob["attack_name"] == "Tir de flèche"
        assert mob["stats"]["hp"]["current"] == 5


@pytest.mark.parametrize("value", [True, 0, 21, float("nan"), "6"])
def test_invalid_attack_range_is_rejected(value):
    mobs = deepcopy(map_building.MOBS)
    mobs["gobelin_archer"] = deepcopy(mobs["goblin"])
    mobs["gobelin_archer"]["attack_range"] = value
    with pytest.raises(ValueError, match="Portée"):
        validate_mobs(mobs)
