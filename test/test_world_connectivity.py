"""Adding connected zones is valid; disconnected or trapping additions still fail."""

from copy import deepcopy

import pytest
from world_checks import assert_connected_world, zone_members

from jeuxRPG.multiplayer.map_layout_editor import layout_places


def growing_world(count):
    maps = {
        "clearing": {
            "name": "Start",
            "zone_id": "home",
            "biome": "forest",
            "sites": [],
            "exits": [],
            "logical_zones": {"home": {"name": "Home"}},
        }
    }
    previous = "clearing"
    for index in range(count):
        zone, key = f"new_zone_{index}", f"new_map_{index}"
        maps["clearing"]["logical_zones"][zone] = {"name": zone}
        maps[key] = {
            "name": key,
            "zone_id": zone,
            "biome": "forest",
            "sites": [],
            "exits": [],
        }
        maps[previous]["exits"].append({"destination": key, "entry": [1, 1]})
        maps[key]["exits"].append({"destination": previous, "entry": [1, 1]})
        previous = key
    return maps


@pytest.mark.parametrize("count", [0, 1, 4, 15])
def test_new_zones_need_no_inventory_update_when_connected(count):
    maps = growing_world(count)
    before = deepcopy(maps)
    assert_connected_world(maps)
    groups = zone_members(maps)
    places = layout_places(maps)
    assert set(places) == set(groups)
    for zone, members in groups.items():
        assert {point["id"] for point in places[zone]["points"]} == members
    assert maps == before


def test_disconnected_addition_is_reported_by_map_name():
    maps = growing_world(2)
    maps["new_map_0"]["exits"] = []
    with pytest.raises(AssertionError, match="unreachable.*new_map_1"):
        assert_connected_world(maps)


def test_connected_map_can_define_its_own_zone_without_separate_metadata():
    maps = growing_world(1)
    maps["clearing"]["logical_zones"].pop("new_zone_0")
    maps["new_map_0"]["zone_id"] = "new_map_0"
    assert_connected_world(maps)
    assert zone_members(maps)["new_map_0"] == {"new_map_0"}
    assert "new_map_0" in layout_places(maps)


def test_a_one_way_passage_is_valid_with_an_alternate_return_path():
    maps = growing_world(2)
    maps["new_map_0"]["exits"] = [{"destination": "new_map_1", "entry": [1, 1]}]
    maps["new_map_1"]["exits"] = [{"destination": "clearing", "entry": [1, 1]}]
    assert_connected_world(maps)


def test_an_accessible_zone_cannot_trap_the_player():
    maps = growing_world(1)
    maps["new_map_0"]["exits"] = []
    with pytest.raises(AssertionError, match="return path.*new_map_0"):
        assert_connected_world(maps)


def test_a_gate_to_an_unknown_map_is_rejected():
    maps = growing_world(0)
    maps["clearing"]["exits"] = [{"destination": "missing", "entry": [1, 1]}]
    with pytest.raises(AssertionError, match="Broken exit.*missing"):
        assert_connected_world(maps)
