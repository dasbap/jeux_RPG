from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import fields, tactics, world
from jeuxRPG.multiplayer.map_assets import validate
from jeuxRPG.multiplayer.map_layout_editor import layout_places
from jeuxRPG.multiplayer.map_world_editor import world_metadata


def route_world():
    maps = deepcopy(fields.MAPS)
    for key in ("clearing", "rosee"):
        maps[key]["exits"].append({"position": [2, 2], "destination": None, "entry": None, "name": "Porte du voyage"})
        for field in ("cover", "blocked", "water"):
            maps[key][field] = [p for p in maps[key].get(field, []) if p != [2, 2]]
    maps["clearing"]["travel_routes"] = [{"id": "custom_route", "name": "Voyage", "from": "clearing", "to": "rosee", "from_entry": [2, 2], "to_entry": [2, 2], "combat_map": "forest", "distance_km": 1}]
    return maps


def test_doors_and_combat_map_round_trip(tmp_path):
    from jeuxRPG.multiplayer import map_assets

    maps = route_world()
    path = tmp_path / "world.json"
    map_assets.save(path, maps)
    assert map_assets.load(path) == maps


@pytest.mark.parametrize("change", [{"to_entry": [999, 2]}, {"combat_map": "missing"}, {"from_entry": [1, 1]}])
def test_invalid_doors_and_missing_combat_map_are_rejected(change):
    maps = route_world()
    maps["clearing"]["travel_routes"][0].update(change)
    with pytest.raises(ValueError):
        validate(maps)


def test_arrival_uses_exact_route_door(monkeypatch):
    maps = route_world()
    monkeypatch.setattr(fields, "MAPS", maps)
    monkeypatch.setattr(world, "ROUTES", maps["clearing"]["travel_routes"])
    monkeypatch.setattr(world, "ROAD_POINTS", {"custom_route": {"zone": "clearing"}})
    assert fields.arrival_point("rosee", "custom_route") == [2, 2]
    assert fields.arrival_point("clearing", "custom_route") == [2, 2]


def test_logical_zone_point_positions_are_preserved():
    maps = deepcopy(fields.MAPS)
    maps["clearing"].setdefault("logical_zones", {})["new_zone"] = {"name": "Zone", "level": 1, "world_view": {"points": {"forest": {"position": [555, 222]}}}}
    maps["forest"]["zone_id"] = "new_zone"
    point = next(p for p in layout_places(maps)["new_zone"]["points"] if p["id"] == "forest")
    assert [point["x"], point["y"]] == [555, 222]


def test_travel_battle_uses_route_map_without_changing_transit(monkeypatch):
    maps = route_world()
    monkeypatch.setattr(world, "ROUTES", maps["clearing"]["travel_routes"])
    monkeypatch.setattr(world, "ROAD_POINTS", {"custom_route": {"zone": "clearing"}})
    monkeypatch.setattr(tactics, "sync_summons", lambda party, now: None)
    party = {"position": "custom_route", "transit": {"source": "clearing", "destination": "custom_route", "remaining": 42}, "characters": {"player": {"level": 1, "stats": {"hp": {"current": 10}}}}, "mobs": [], "encounter_number": 1}
    transit = deepcopy(party["transit"])
    tactics.begin(party, 0, "travel")
    assert party["battle"]["preset"] == "field_forest"
    assert party["transit"] == transit
    preset = tactics.PRESETS["field_forest"]
    assert tactics.walkable(preset, party["battle"]["players"]["player"]["position"])
