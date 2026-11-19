import json
from copy import deepcopy

import pytest
import test_zone_navigation

from jeuxRPG.multiplayer import fields, spawn_cycles, tutorial
from jeuxRPG.multiplayer.controller_gameplay import change
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.service import GameError

coach_network = test_zone_navigation.coach_network
network = test_zone_navigation.network


@pytest.fixture
def group(network, monkeypatch):
    data = network.maps["clearing"]
    config = deepcopy(data["spawners"][0])
    config.update(count=3, respawn_profile="default")
    data["spawns"] = [config["position"]]
    data["spawners"] = [config]
    party = tutorial.new_party([{"id": "p", "name": "Cycle", "class_name": "Knight"}])
    party["field_mode"] = True
    fields.enter(party, "clearing", config["position"], 0)
    return network, party


def kill_all(party, now=0):
    for mob in party["mobs"][:]:
        party["mobs"].remove(mob)
        spawn_cycles.on_death(party, mob, now)


def test_group_of_three_refills_one_each_40_real_seconds_and_never_overflows(group):
    project, party = group
    start = party["battle"]["started_at"]
    kill_all(party)
    for now, count in [
        (119, 0),
        (120, 1),
        (239, 1),
        (240, 2),
        (359, 2),
        (360, 3),
        (10000, 3),
    ]:
        spawn_cycles.advance(party, "clearing", now)
        assert len(party["mobs"]) == count
        assert party["battle"]["started_at"] == start
    assert len({m["combat_id"].split(":repop:")[0] for m in party["mobs"]}) == 3


def test_cycle_persists_after_reload_and_catches_up_only_to_capacity(group):
    _, party = group
    kill_all(party, 10)
    party = json.loads(json.dumps(party))
    spawn_cycles.advance(party, "clearing", 129)
    assert not party["mobs"]
    spawn_cycles.advance(party, "clearing", 10000)
    assert len(party["mobs"]) == 3
    spawn_cycles.advance(party, "clearing", 20000)
    assert len(party["mobs"]) == 3


def test_profile_override_disable_and_remote_survivor_are_respected(group):
    project, party = group
    config = project.maps["clearing"]["spawners"][0]
    config["respawn_profile"] = "boss"
    kill_all(party)
    spawn_cycles.advance(party, "clearing", 599)
    assert not party["mobs"]
    spawn_cycles.advance(party, "clearing", 600)
    assert len(party["mobs"]) == 1
    config["respawn_seconds"] = 60
    spawn_cycles.advance(party, "clearing", 600)
    spawn_cycles.advance(party, "clearing", 659)
    assert len(party["mobs"]) == 1
    spawn_cycles.advance(party, "clearing", 660)
    assert len(party["mobs"]) == 2
    remote = party["mobs"].pop()
    party["fields"]["rosee"] = {"mobs": [remote], "battle": {"arrivals": []}}
    spawn_cycles.advance(party, "clearing", 720)
    assert len(party["mobs"]) == 2
    config["respawn_seconds"] = 0
    kill_all(party, 720)
    spawn_cycles.advance(party, "clearing", 10000)
    assert not party["mobs"]


def test_builder_profiles_and_spawner_validation_survive_save(group, tmp_path):
    project, _ = group
    change(
        project,
        "respawn_profiles",
        "warrior",
        {"name": "Guerrier rapide", "seconds": 90},
    )
    project.maps["clearing"]["spawners"][0].update(
        respawn_profile="warrior", respawn_seconds=75
    )
    copied = Project(tmp_path / "project")
    copied.restore(project.state())
    copied.save()
    reopened = Project(tmp_path / "project")
    assert reopened.content["gameplay"]["respawn_profiles"]["warrior"]["seconds"] == 90
    assert reopened.maps["clearing"]["spawners"][0]["respawn_seconds"] == 75
    for value in (-1, True, float("inf"), "120"):
        config = deepcopy(project.maps["clearing"]["spawners"][0])
        config["respawn_seconds"] = value
        with pytest.raises(ValueError):
            spawn_cycles.validate_spawner(config)
    before = project.state()
    with pytest.raises(ValueError):
        change(project, "respawn_profiles", "default", delete=True)
    assert project.state() == before


def test_harvest_requires_range_and_only_pays_once(group):
    _, party = group
    unit = party["battle"]["players"]["p"]
    position = unit["position"][:]
    party["battle"]["corpses"] = [
        {
            "id": "body",
            "name": "Gobelin",
            "position": [position[0] + 5, position[1]],
            "loot": {"peau": 2},
            "harvested": [],
        }
    ]
    before = deepcopy(party["inventory"])
    with pytest.raises(GameError):
        tutorial.execute(
            party, "p", "harvest", {"target": "body"}, 100, GameError, lambda: 1
        )
    assert party["inventory"] == before
    party["battle"]["corpses"][0]["position"] = position
    tutorial.execute(
        party, "p", "harvest", {"target": "body"}, 100, GameError, lambda: 1
    )
    assert party["inventory"]["p"].get("peau", 0) == before["p"].get("peau", 0) + 2
    with pytest.raises(GameError):
        tutorial.execute(
            party, "p", "harvest", {"target": "body"}, 110, GameError, lambda: 1
        )
    assert party["inventory"]["p"].get("peau", 0) == before["p"].get("peau", 0) + 2


def test_away_from_map_keeps_death_schedule_and_profile_edits_do_not_reset_mobs(group):
    project, party = group
    from jeuxRPG.multiplayer.field_spawners import manifest

    before = manifest(project.maps["clearing"], project.maps, "clearing")
    config = project.maps["clearing"]["spawners"][0]
    config["respawn_profile"] = "warrior"
    assert manifest(project.maps["clearing"], project.maps, "clearing") == before
    kill_all(party, 0)
    party["fields"]["clearing"] = fields.snapshot(party, 0)
    fields.enter(party, "rosee", [42, 28], 10)
    fields.enter(party, "clearing", config["position"], 240)
    spawn_cycles.advance(party, "clearing", 240)
    assert len(party["mobs"]) == 2
    spawn_cycles.advance(party, "clearing", 360)
    assert len(party["mobs"]) == 3


def test_pursuer_killed_on_another_map_keeps_its_original_spawner_schedule(group):
    project, party = group
    mob = party["mobs"].pop()
    party["fields"]["clearing"] = fields.snapshot(party, 0)
    fields.enter(party, "rosee", [42, 28], 10)
    spawn_cycles.on_death(party, mob, 10)
    timer = next(iter(party["spawn_timers"]["clearing"].values()))
    assert timer["next_at"] == 130
    fields.enter(
        party, "clearing", project.maps["clearing"]["spawners"][0]["position"], 130
    )
    spawn_cycles.advance(party, "clearing", 130)
    assert len(party["mobs"]) == 3
