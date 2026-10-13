from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeuxRPG.multiplayer import fields
from jeuxRPG.multiplayer.map_world_editor import WorldEditor, add_travel_door, world_metadata


def empty_maps():
    maps = deepcopy(fields.MAPS)
    for key in ("clearing", "rosee"):
        for field in ("cover", "blocked", "water", "sites"):
            maps[key][field] = []
        maps[key]["exits"] = [g for g in maps[key]["exits"] if g["position"] != [2, 2]]
    return maps


def test_click_creates_door_and_reusing_it_does_not_duplicate():
    maps = empty_maps()
    add_travel_door(maps, "clearing", [2, 2])
    add_travel_door(maps, "clearing", [2, 2])
    doors = [g for g in maps["clearing"]["exits"] if g["position"] == [2, 2]]
    assert len(doors) == 1
    assert doors[0]["destination"] is None


@pytest.mark.parametrize("field", ["cover", "blocked", "water", "sites", "exits"])
def test_click_cannot_replace_obstacle_npc_or_existing_passage(field):
    maps = empty_maps()
    if field == "sites":
        maps["clearing"][field].append({"position": [2, 2]})
    elif field == "exits":
        maps["clearing"][field].append({"position": [2, 2], "destination": "rosee"})
    else:
        maps["clearing"][field].append([2, 2])
    before = deepcopy(maps)
    with pytest.raises(ValueError):
        add_travel_door(maps, "clearing", [2, 2])
    assert maps == before


def test_route_editor_stages_graphically_created_doors_until_apply():
    maps = empty_maps()
    before = deepcopy(maps)
    values = {"route_id": "new_trip", "name": "Voyage", "from_map": "clearing", "to_map": "rosee", "from_entry": "2,2", "to_entry": "2,2", "from_create_door": True, "to_create_door": True, "combat_map": "", "distance_km": "0.1", "travel_minutes": "1"}
    editor = WorldEditor.__new__(WorldEditor)
    editor.editor = SimpleNamespace(maps=maps, form=lambda *args: values)
    editor.roads = SimpleNamespace(curselection=lambda: ())
    editor.routes = []
    editor.pending_doors = []
    editor.streets = {}
    editor.rules = {"movement": {"walking_kmh": 6}}
    editor.refresh = lambda: None
    editor.road(new=True)
    assert maps == before
    assert editor.pending_doors == [("clearing", [2, 2]), ("rosee", [2, 2])]
    candidate = deepcopy(maps)
    for map_id, point in editor.pending_doors:
        add_travel_door(candidate, map_id, point)
    candidate["clearing"]["travel_routes"] = editor.routes
    assert world_metadata(candidate, {}, editor.routes)[1] == editor.routes
