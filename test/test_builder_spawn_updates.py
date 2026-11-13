"""Existing solo visits follow Builder edits without reviving unchanged defeated mobs."""

from copy import deepcopy

import pytest
from test_fields import (
    party,
    stable_field_scenarios,  # noqa: F401
)

from jeuxRPG.multiplayer import fields, map_building, tactics, tutorial

pytestmark = pytest.mark.usefixtures("stable_field_scenarios")


def spawn_at(definition, position, count=1, mob_id="goblin"):
    definition["spawns"].append(position)
    definition.setdefault("spawners", []).append(
        {"position": position, "mob_id": mob_id, "count": count}
    )


def test_legacy_empty_visit_receives_new_spawners_without_resetting_character():
    data = party()
    definition = fields.MAPS["lisiere"]
    definition.update(spawns=[], spawners=[])
    fields.enter(data, "lisiere", [1, 10], 0)
    data["battle"].pop("spawn_manifest")
    before = deepcopy(data["characters"])
    data["inventory"]["peau"] = 9
    spawn_at(definition, [10, 10], 2)
    spawn_at(definition, [14, 10], 3)
    tutorial.migrate(data, 100)
    assert len(data["mobs"]) == 5
    assert all(mob["next_attack"] == 106 for mob in data["mobs"])
    assert data["characters"] == before and data["inventory"]["peau"] == 9
    assert data["field_map"] == "lisiere"
    ids = {mob["combat_id"] for mob in data["mobs"]}
    tutorial.migrate(data, 101)
    assert ids == {mob["combat_id"] for mob in data["mobs"]}


def test_unchanged_builder_does_not_respawn_a_defeated_mob():
    data = party()
    mob = data["mobs"].pop()
    data["battle"]["corpses"].append(
        {"id": mob["combat_id"], "position": mob["position"]}
    )
    tutorial.sync_mobs(data)
    before = deepcopy(data["mobs"])
    tutorial.migrate(data, 5)
    assert data["mobs"] == before


def test_new_spawner_does_not_revive_unchanged_defeated_group():
    data = party()
    data["mobs"] = []
    tutorial.sync_mobs(data)
    spawn_at(fields.MAPS["clearing"], [10, 10], 2, "orc")
    tutorial.migrate(data, 3)
    assert len(data["mobs"]) == 2
    assert all(mob["mob_id"] == "orc" for mob in data["mobs"])


def test_species_count_level_hostility_and_removed_spawners_follow_builder():
    data = party()
    definition = fields.MAPS["lisiere"]
    definition.update(spawns=[], spawners=[])
    spawn_at(definition, [10, 10], 2)
    fields.enter(data, "lisiere", [1, 10], 0)
    config = definition["spawners"][0]
    config.update(
        mob_id="orc", count=3, level=4, hostile=False, patrol=[[10, 10], [11, 10]]
    )
    tutorial.migrate(data, 20)
    assert len(data["mobs"]) == 3
    assert all(
        mob["mob_id"] == "orc" and mob["level"] == 4 and not mob["hostile"]
        for mob in data["mobs"]
    )
    assert all(mob["patrol_route"] == config["patrol"] for mob in data["mobs"])
    definition.update(spawns=[], spawners=[])
    tutorial.migrate(data, 21)
    assert not data["mobs"] and data["mob"] is None
    assert data["battle"]["players"]


def test_cached_visit_receives_builder_edits_when_reentered():
    data = party()
    definition = fields.MAPS["lisiere"]
    definition.update(spawns=[], spawners=[])
    fields.enter(data, "lisiere", [1, 10], 0)
    data["fields"]["lisiere"] = fields.snapshot(data, 1)
    fields.enter(data, "rosee", [1, 20], 2)
    spawn_at(definition, [12, 10], 3)
    fields.enter(data, "lisiere", [1, 10], 3)
    assert len(data["mobs"]) == 3


def test_species_definition_changes_update_the_existing_field(monkeypatch):
    data = party()
    changed = deepcopy(map_building.MOBS)
    changed["goblin"]["hostile"] = False
    monkeypatch.setattr(map_building, "MOBS", changed)
    tutorial.migrate(data, 10)
    assert data["mobs"] and all(not mob["hostile"] for mob in data["mobs"])
    assert tactics.view(data, 10)["hostiles_alive"] == 0
