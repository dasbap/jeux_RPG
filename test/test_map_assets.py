import json
from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import fields, map_assets, tactics, tutorial
from jeuxRPG.multiplayer.service import GameError


def maps():
    return deepcopy(fields.MAPS)


def test_map_file_roundtrip_and_atomic_save(tmp_path):
    path = tmp_path / "maps.json"
    data = maps()
    data["rosee"]["sites"].append({"id": "guide", "name": "Guide", "position": [33, 20], "dialogue": "Suivez-moi", "owner": "leader"})
    map_assets.save(path, data)
    assert map_assets.load(path) == data
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("change", [
    lambda d: d["clearing"]["spawns"].append([200, 1]),
    lambda d: d["clearing"]["spawns"].append(d["clearing"]["cover"][0]),
    lambda d: d["clearing"]["exits"][0].update(destination="unknown"),
    lambda d: d["clearing"]["exits"][0].update(destination="rosee", entry=[200, 1]),
    lambda d: d["rosee"]["sites"].append(deepcopy(d["rosee"]["sites"][0])),
    lambda d: d.pop("clearing"),
    lambda d: d["clearing"].update(width=10000),
    lambda d: d["clearing"].update(exits=[]),
])
def test_invalid_map_is_rejected_without_overwriting_file(tmp_path, change):
    path = tmp_path / "maps.json"
    map_assets.save(path, maps())
    before = path.read_bytes()
    data = maps()
    change(data)
    with pytest.raises(ValueError):
        map_assets.save(path, data)
    assert path.read_bytes() == before


def test_water_separating_exit_is_rejected():
    data = maps()
    definition = data["clearing"]
    definition["blocked"] += [[28, y] for y in range(definition["height"])]
    with pytest.raises(ValueError, match="inaccessible"):
        map_assets.validate(data)


def test_custom_map_and_teleport_are_validated():
    data = maps()
    data["custom"] = fields.terrain("custom", "Jardin", 10, 10, [], [fields.gate(0, 5, "rosee", [1, 20], "Rosée")])
    data["rosee"]["exits"].append(fields.gate(1, 20, "custom", [1, 5], "Jardin"))
    assert "custom" in map_assets.validate(data)


def test_configured_maps_require_valid_json(tmp_path, monkeypatch):
    path = tmp_path / "maps.json"
    path.write_text(json.dumps(maps()))
    monkeypatch.setenv("RPG_MAPS_FILE", str(path))
    configured = map_assets.configured({})
    assert all(definition.pop("terrain_version") for definition in configured.values())
    expected = maps()
    for definition in expected.values():
        definition.pop("terrain_version", None)
    assert configured == expected
    path.write_text('{}')
    with pytest.raises(ValueError):
        map_assets.configured(maps())


def test_linked_npc_follows_and_crosses_maps(monkeypatch):
    data = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    fields.start(data, 0)
    definition = deepcopy(fields.MAPS["clearing"])
    definition["sites"].append({"id": "guide", "name": "Guide", "position": [1, 8], "owner": "leader", "dialogue": "Bonjour"})
    monkeypatch.setitem(fields.MAPS, "clearing", definition)
    monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)
    data["mobs"] = []
    data["battle"]["players"]["p"]["position"] = [6, 10]
    characters = {key: tutorial.unpack(actor) for key, actor in data["characters"].items()}
    tactics.advance_companions(data, characters, definition, 0)
    npc = data["battle"]["companions"]["guide"]
    assert npc["owner"] == "p"
    assert tactics.distance(npc["position"], [6, 10]) < tactics.distance([1, 8], [6, 10])
    before = npc["position"][:]
    tactics.advance_companions(data, characters, definition, .1)
    assert npc["position"] == before
    fields.enter(data, "rosee", [1, 20], 2)
    npc = data["battle"]["companions"]["guide"]
    assert tactics.distance(npc["position"], data["battle"]["players"]["p"]["position"]) <= 2
    data["mobs"] = []
    assert fields.execute(data, "p", "talk", {"npc": "guide"}, 2, GameError, lambda: .5)[0] == ["Guide : Bonjour"]
    data["battle"]["players"]["p"]["position"] = [10, 20]
    with pytest.raises(GameError):
        fields.execute(data, "p", "talk", {"npc": "guide"}, 2, GameError, lambda: .5)
    assert any(site["id"] == "guide" for site in tactics.view(data, 2, "p")["map"]["sites"])


def test_graphical_editor_painting_undo_and_object_properties():
    from jeuxRPG.multiplayer.map_editor import MapEditor
    from types import SimpleNamespace
    class Variable:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value
        def set(self, value):
            self.value = value
    class Canvas:
        def canvasx(self, value):
            return value
        def canvasy(self, value):
            return value
    editor = MapEditor.__new__(MapEditor)
    editor.maps = maps()
    editor.history = []
    editor.size = 24
    editor.selected = Variable("clearing")
    editor.tool = Variable("Eau")
    editor.canvas = Canvas()
    editor.choice = SimpleNamespace(configure=lambda **values: None)
    editor.draw = lambda: None
    event = SimpleNamespace(x=48, y=240)
    editor.click(event)
    assert [2, 10] in editor.maps["clearing"]["blocked"]
    assert not tactics.walkable(editor.maps["clearing"], [2, 10])
    editor.tool.set("Pont")
    editor.click(event)
    assert tactics.walkable(editor.maps["clearing"], [2, 10])
    assert [2, 10] in editor.maps["clearing"]["bridges"]
    editor.undo()
    assert [2, 10] in editor.maps["clearing"]["blocked"]
    editor.tool.set("Sol")
    editor.click(event)
    editor.tool.set("Téléportation")
    editor.form = lambda title, values: {"name": "Rosée", "destination": "rosee", "entry": "1,20"}
    editor.click(event)
    assert editor.maps["clearing"]["exits"][-1]["entry"] == [1, 20]
    editor.tool.set("PNJ")
    editor.form = lambda title, values: {"id": "guide", "name": "Guide", "dialogue": "Bienvenue", "owner": "leader"}
    editor.click(SimpleNamespace(x=72, y=240))
    assert editor.maps["clearing"]["sites"][-1]["owner"] == "leader"
    map_assets.validate(editor.maps)


def test_graphical_editor_draws_grid_decorations_and_entities():
    from jeuxRPG.multiplayer.map_editor import MapEditor
    from types import SimpleNamespace
    editor = MapEditor.__new__(MapEditor)
    editor.maps = maps()
    editor.selected = SimpleNamespace(get=lambda: "rosee")
    editor.size = 24
    rectangles, labels = [], []
    editor.canvas = SimpleNamespace(delete=lambda *args: None, configure=lambda **values: None,
        create_rectangle=lambda *args, **values: rectangles.append(values),
        create_text=lambda *args, **values: labels.append(values))
    editor.draw()
    definition = editor.maps["rosee"]
    assert len(rectangles) == definition["width"] * definition["height"]
    assert any(rectangle["fill"] == "#348aba" for rectangle in rectangles)
    assert any(label["text"] == "↗" for label in labels)
    assert any(label["text"] == "N" for label in labels)


def test_modified_terrain_relocates_existing_companion(monkeypatch):
    data = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    fields.start(data, 0)
    data["battle"]["companions"] = {"guide": {"id": "guide", "position": [2, 10], "owner": "p", "name": "Guide"}}
    definition = deepcopy(fields.MAPS["clearing"])
    definition["blocked"].append([2, 10])
    definition["terrain_version"] = "edited"
    monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)
    fields.migrate_terrain(data)
    assert data["battle"]["terrain_version"] == "edited"
    assert tactics.walkable(definition, data["battle"]["companions"]["guide"]["position"])


def test_editor_renames_display_name_and_keeps_map_identifier():
    from jeuxRPG.multiplayer.map_editor import MapEditor
    from types import SimpleNamespace
    editor = MapEditor.__new__(MapEditor)
    editor.maps = maps()
    editor.selected = SimpleNamespace(get=lambda: "rosee")
    editor.choice = SimpleNamespace(configure=lambda **values: None)
    editor.history = []
    editor.draw = lambda: None
    editor.form = lambda title, values: {"name": "Rosée renommée", "width": "64", "height": "40", "biome": "village"}
    editor.properties()
    assert editor.maps["rosee"]["name"] == "Rosée renommée"
    assert editor.map_labels["Rosée renommée [rosee] · niv. 1"] == "rosee"
    assert editor.maps["rosee"]["id"] == "field_rosee"


def test_editor_creates_practicable_bidirectional_gate():
    from jeuxRPG.multiplayer.map_editor import MapEditor
    from types import SimpleNamespace
    editor = MapEditor.__new__(MapEditor)
    editor.maps = maps()
    editor.selected = SimpleNamespace(get=lambda: "clearing")
    editor.set_gate([2, 10], {"name": "Rosée", "destination": "rosee", "entry": "2,20", "bidirectional": True})
    reverse = editor.maps["rosee"]["exits"][-1]
    assert reverse["destination"] == "clearing"
    assert reverse["position"] != [2, 20]
    assert reverse["entry"] != [2, 10]
    map_assets.validate(editor.maps)


def test_editor_complete_exit_ignores_unused_arrival_and_preserves_origin():
    from jeuxRPG.multiplayer.map_editor import MapEditor
    from types import SimpleNamespace
    editor = MapEditor.__new__(MapEditor)
    editor.maps = maps()
    editor.selected = SimpleNamespace(get=lambda: "clearing")
    editor.set_gate([2, 10], {"name": "Sortie", "destination": "", "entry": "", "fast_destination": "rosee"})
    assert editor.maps["clearing"]["exits"][-1]["entry"] is None
    assert editor.maps["clearing"]["exits"][-1]["fast_destination"] == "rosee"
    before = deepcopy(editor.maps)
    with pytest.raises(ValueError):
        editor.set_gate([3, 10], {"name": "Erreur", "destination": "rosee", "entry": "0,20"})
    assert editor.maps == before


def test_json_directory_combines_field_files_and_excludes_encounters(tmp_path):
    data = maps()
    forest = {key: value for key, value in data.items() if key.startswith("clearing")}
    rest = {key: value for key, value in data.items() if key not in forest}
    (tmp_path / "forest.json").write_text(json.dumps(forest))
    (tmp_path / "villages.json").write_text(json.dumps(rest))
    (tmp_path / "encounters.json").write_text(json.dumps({"kind": "encounters", "maps": {"test": {}}}))
    assert map_assets.load(tmp_path) == data
    (tmp_path / "duplicate.json").write_text(json.dumps(forest))
    with pytest.raises(ValueError, match="dupliquée"):
        map_assets.load(tmp_path)
