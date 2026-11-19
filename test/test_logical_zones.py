import json
from copy import deepcopy
from pathlib import Path

import pytest
from world_checks import assert_connected_world, zone_members

from jeuxRPG.multiplayer import fields, map_assets
from jeuxRPG.multiplayer.map_building import map_level, zone_of
from jeuxRPG.multiplayer.map_layout_editor import layout_places


def test_mapless_zone_can_contain_multiple_maps_and_be_saved(tmp_path):
    maps = deepcopy(fields.MAPS)
    maps["clearing"].setdefault("logical_zones", {}).update(
        {
            "grotte_oublies": {
                "name": "Grotte des Oubliés",
                "level": 5,
                "world_view": {"position": [450, 300]},
            }
        }
    )
    maps["cave_1"]["zone_id"] = "grotte_oublies"
    maps["cave_2"]["zone_id"] = "grotte_oublies"

    assert zone_of(maps, "cave_1") == "grotte_oublies"
    assert zone_of(maps, "cave_2") == "grotte_oublies"
    maps["cave_1"].pop("level", None)
    assert map_level(maps, "cave_1") == 5

    places = layout_places(maps)
    assert places["grotte_oublies"]["name"] == "Grotte des Oubliés"
    assert (places["grotte_oublies"]["x"], places["grotte_oublies"]["y"]) == (450, 300)
    assert {"cave_1", "cave_2"} <= {p["id"] for p in places["grotte_oublies"]["points"]}

    path = tmp_path / "world.json"
    map_assets.save(path, maps)
    assert map_assets.load(path) == maps


def test_logical_zone_must_exist_and_have_valid_level():
    maps = deepcopy(fields.MAPS)
    maps["clearing"]["logical_zones"] = {
        "grotte_oublies": {"name": "Grotte des Oubliés", "level": 101}
    }
    with pytest.raises(ValueError):
        map_assets.validate(maps)

    maps["clearing"]["logical_zones"]["grotte_oublies"]["level"] = 5
    maps["cave_1"]["zone_id"] = "missing_zone"
    with pytest.raises(ValueError):
        map_assets.validate(maps)


def test_packaged_world_uses_the_authored_logical_zones():
    data = json.loads(Path("jeuxRPG/maps/world.json").read_text(encoding="utf-8"))
    maps = data.get("maps", data)
    assert_connected_world(maps)
    expected = zone_members(maps)
    logical = maps["clearing"]["logical_zones"]
    assert set(logical) <= set(expected)
    for zone_id, members in expected.items():
        assert {key for key in maps if zone_of(maps, key) == zone_id} == members
    assert "zone_level" not in maps["clearing"]
    assert "zone_level" not in maps["rosee"]
    places = layout_places(maps)
    assert set(expected) == set(places)
    assert "clearing" not in places
    assert "rosee" not in places
    assert "grotte_oublies" in places


def test_packaged_hunt_counts_goblins_in_its_logical_zone():
    from jeuxRPG.multiplayer import content, tutorial, world
    from jeuxRPG.multiplayer.map_building import MOBS

    content.validate_references(content.DATA, MOBS, fields.MAPS)

    party = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    content.quest_dialogue(party, "mira")
    hunt = content.HUNT
    assert hunt["zone"] == world.zone_of("hunt")
    party.update(position="forest", field_map="forest")
    content.quest_event(party, "kill", "goblin", world.zone_of("forest"))
    assert content.quest_states(party)[hunt["id"]]["progress"] == 0
    party.update(position="hunt", field_map="hunt")
    content.quest_event(party, "kill", "goblin", world.zone_of("hunt"))
    assert content.quest_states(party)[hunt["id"]]["progress"] == 1
