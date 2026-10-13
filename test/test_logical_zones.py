from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import fields, map_assets
from jeuxRPG.multiplayer.map_building import map_level, zone_of
from jeuxRPG.multiplayer.map_layout_editor import layout_places


def test_mapless_zone_can_contain_multiple_maps_and_be_saved(tmp_path):
    maps = deepcopy(fields.MAPS)
    maps["clearing"]["logical_zones"] = {
        "grotte_oublies": {
            "name": "Grotte des Oubliés",
            "level": 5,
            "world_view": {"position": [450, 300]},
        }
    }
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
