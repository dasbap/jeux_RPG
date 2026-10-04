from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import fields, map_assets, map_building, tactics, tutorial, world
from jeuxRPG.multiplayer.map_editor import MapEditor


@pytest.fixture(autouse=True)
def stable_builder_scenarios(monkeypatch):
    data = json.loads((Path(__file__).parent / 'fixtures' / 'fields.json').read_text())
    monkeypatch.setattr(fields, 'MAPS', data)
    places = deepcopy(world.PLACES)
    for key, definition in data.items():
        zone = fields.zone_of(data, key)
        if key != zone and not any(point['id'] == key for place in places.values() for point in place['points']):
            places[zone]['points'].append({'id': key, 'name': definition['name'], 'kind': 'field'})
    monkeypatch.setattr(world, 'PLACES', places)
    for definition in data.values():
        monkeypatch.setitem(tactics.PRESETS, definition['id'], definition)


def editor():
    e = MapEditor.__new__(MapEditor)
    e.maps = deepcopy(fields.MAPS)
    e.selected = SimpleNamespace(get=lambda: "clearing")
    e.history = []
    e.draw = lambda: None
    e.size = 24
    e.choice = SimpleNamespace(configure=lambda **values: None)
    e.canvas = SimpleNamespace(canvasx=lambda value: value, canvasy=lambda value: value)
    return e


def test_zone_level_inheritance_local_and_spawner_overrides():
    maps = deepcopy(fields.MAPS)
    maps["clearing"]["zone_level"] = 7
    assert map_building.map_level(maps, "clearing_trail") == 7
    maps["clearing_trail"]["level"] = 3
    assert map_building.map_level(maps, "clearing_trail") == 3
    mob = map_building.create_mob(maps, "clearing_trail", {"mob_id": "orc", "level": 5}, 0)
    assert mob["level"] == 5
    assert mob["class_name"] == "Orc"
    assert mob["stats"]["hp"]["current"] == mob["stats"]["hp"]["max"]
    assert map_building.create_mob(maps, "clearing_trail", {"mob_id": "goblin"}, 0)["level"] == 3


@pytest.mark.parametrize("change", [
    lambda m: m["clearing"].update(zone_id="clearing_trail"),
    lambda m: m["clearing"].update(zone_id="unknown"),
    lambda m: m["clearing"].update(zone_level=0),
    lambda m: m["clearing"]["spawners"][0].update(mob_id="Knight"),
    lambda m: m["clearing"]["spawners"][0].update(level=101),
    lambda m: m["clearing"]["spawners"][0].update(count=0),
    lambda m: m["clearing"]["spawners"][0].update(patrol=[[999, 999]]),
])
def test_invalid_zone_spawner_and_patrol_are_rejected(change):
    maps = deepcopy(fields.MAPS)
    change(maps)
    with pytest.raises(ValueError):
        map_assets.validate(maps)


def test_different_spawners_and_groups_create_correct_entities_and_repop(monkeypatch):
    maps = deepcopy(fields.MAPS)
    definition = maps["clearing_road"]
    definition["spawns"] = [[8, 10], [24, 10]]
    definition["spawners"] = [{"position": [8, 10], "mob_id": "orc", "level": 3, "count": 2, "patrol": [[8, 10], [9, 10]]}, {"position": [24, 10], "mob_id": "dragon_whelp", "level": 4}]
    map_assets.validate(maps)
    monkeypatch.setitem(fields.MAPS, "clearing_road", definition)
    monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)
    party = tutorial.new_party([dict(id="p", name="Test", class_name="Knight")])
    fields.start(party, 0)
    fields.enter(party, "clearing_road", [1, 10], 1)
    assert [(mob["class_name"], mob["level"]) for mob in party["mobs"]] == [("Orc", 3), ("Orc", 3), ("DragonWhelp", 4)]
    assert len({tuple(mob["position"]) for mob in party["mobs"]}) == 3
    assert party["mobs"][0]["patrol_route"] == [[8, 10], [9, 10]]
    party["mobs"].pop()
    fields.repop(party, "clearing_road", 200)
    assert [(mob["class_name"], mob["level"]) for mob in party["mobs"]][-1] == ("DragonWhelp", 4)
    snapshot = tutorial.view(party, "p", 201)
    assert {creature["id"] for creature in snapshot["world"]["bestiary"]} >= {"orc", "dragon_whelp"}


def test_walls_and_barricades_block_movement_and_sight():
    e = editor()
    e.tool = SimpleNamespace(get=lambda: "Rempart X")
    e.click(SimpleNamespace(x=48, y=240))
    definition = e.maps["clearing"]
    assert not tactics.walkable(definition, [2, 10])
    assert not tactics.sight(definition, [1, 10], [3, 10])
    assert any(d["kind"] == "barricade" and d["position"] == [2, 10] for d in definition["decorations"])
    e.tool = SimpleNamespace(get=lambda: "Mur M")
    e.click(SimpleNamespace(x=48, y=240))
    assert any(d["kind"] == "wall" and d["position"] == [2, 10] for d in definition["decorations"])


def test_search_filters_by_text_zone_and_level():
    e = editor()
    e.search = SimpleNamespace(get=lambda: "forêt")
    e.zone_filter = SimpleNamespace(get=lambda: "clearing")
    e.min_level = SimpleNamespace(get=lambda: "1")
    e.max_level = SimpleNamespace(get=lambda: "2")
    e.refresh_choice()
    assert set(e.map_labels.values()) == {"clearing", "clearing_trail", "clearing_road"}
    e.min_level = SimpleNamespace(get=lambda: "10")
    e.refresh_choice()
    assert not e.map_labels


def test_overlap_sync_copies_terrain_without_entities():
    e = editor()
    point = [28, 4]
    source = e.maps["clearing"]
    source["cover"].append(point)
    source["decorations"].append({"position": point, "kind": "wall"})
    exits = deepcopy(e.maps["clearing_trail"]["exits"])
    assert map_building.sync_overlap(e.maps, "clearing") == 1
    target = e.maps["clearing_trail"]
    assert [2, 4] in target["cover"]
    assert {"position": [2, 4], "kind": "wall"} in target["decorations"]
    assert target["exits"] == exits


def test_editor_generic_spawner_updates_existing_species_and_level():
    e = editor()
    e.tool = SimpleNamespace(get=lambda: "Spawn")
    e.form = lambda title, values: {"mob_id": "orc", "level": "4", "count": "2", "name": "Garde"}
    e.click(SimpleNamespace(x=408, y=240))
    config = next(c for c in e.maps["clearing"]["spawners"] if c["position"] == [17, 10])
    assert (config["mob_id"], config["level"], config["count"]) == ("orc", 4, 2)
    assert e.maps["clearing"]["spawns"].count([17, 10]) == 1


def test_large_brush_paints_once_and_undo_restores_the_stroke():
    e = editor()
    e.tool = SimpleNamespace(get=lambda: "Mur M")
    e.brush = SimpleNamespace(get=lambda: "3")
    before = deepcopy(e.maps)
    draws = []
    e.draw = lambda: draws.append(True)
    e.click(SimpleNamespace(x=48, y=240))
    assert len(draws) == 1
    assert all([x, y] in e.maps["clearing"]["cover"] for x in range(2, 5) for y in range(10, 13))
    e.undo()
    assert e.maps == before


def test_editor_patrol_points_are_persisted(monkeypatch):
    from jeuxRPG.multiplayer import map_editor
    e = editor()
    e.tool = SimpleNamespace(get=lambda: "Patrouille")
    monkeypatch.setattr(map_editor, "messagebox", SimpleNamespace(askyesno=lambda *args: True), raising=False)
    e.click(SimpleNamespace(x=408, y=240))
    e.click(SimpleNamespace(x=432, y=192))
    assert e.maps["clearing"]["spawners"][0]["patrol"] == [[18, 8]]
    map_assets.validate(e.maps)


def test_duplicate_does_not_share_mutable_data_or_overlap_origin(monkeypatch):
    from jeuxRPG.multiplayer import map_editor
    e = editor()
    selection = ["clearing"]
    e.selected = SimpleNamespace(get=lambda: selection[0], set=lambda value: selection.__setitem__(0, value))
    monkeypatch.setattr(e, "form", lambda *args: {"map_id": "copie"})
    e.duplicate()
    clone = e.maps["copie"]
    assert clone["id"] == "field_copie"
    assert "world_origin" not in clone
    assert clone["zone_id"] == "clearing"
    clone["spawners"][0]["mob_id"] = "orc"
    assert e.maps["clearing"]["spawners"][0]["mob_id"] == "goblin"


@pytest.mark.parametrize('direction', ['est', 'ouest', 'nord', 'sud'])
def test_create_linked_sector_has_safe_return_and_shared_zone(direction):
    original = deepcopy(fields.MAPS)
    result = map_building.linked_sector(original, 'clearing_road', 'new_sector', direction, 4)
    target = result['new_sector']
    assert map_building.zone_of(result, 'new_sector') == 'clearing'
    assert original == fields.MAPS
    back = target['exits'][0]
    forward = next(g for g in result['clearing_road']['exits'] if g['destination'] == 'new_sector')
    assert back['destination'] == 'clearing_road'
    assert tactics.walkable(target, forward['entry'])
    assert tactics.walkable(result['clearing_road'], back['entry'])
    assert back['position'] != forward['entry']
    assert forward['position'] != back['entry']
    assert target['world_origin'] != result['clearing_road']['world_origin']


def test_linked_sector_invalid_overlap_does_not_mutate_source():
    original = deepcopy(fields.MAPS)
    with pytest.raises(ValueError):
        map_building.linked_sector(original, 'clearing', 'new_sector', 'est', 99)
    assert original == fields.MAPS
