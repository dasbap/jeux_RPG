import json
from pathlib import Path
from types import SimpleNamespace

from jeuxRPG.multiplayer.map_layout_editor import LayoutEditor, layout_places


def test_local_and_packaged_world_group_maps_into_five_zones():
    for path in ("projects/authored/world.json", "jeuxRPG/maps/world.json"):
        data = json.loads(Path(path).read_text())
        maps = data.get("maps", data)
        places = layout_places(maps)
        assert set(places) == {"foret_eveilles", "zone_rosee", "zone_lisiere", "zone_brume", "grotte_oublies"}
        assert {p["id"] for p in places["zone_rosee"]["points"]} == {"rosee", "forest"}
        assert {p["id"] for p in places["zone_lisiere"]["points"]} == {"lisiere", "hunt"}
        assert {p["id"] for p in places["zone_brume"]["points"]} == {"brume"}
        assert {p["id"] for p in places["grotte_oublies"]["points"]} == {"cave_1", "cave_2"}
        assert all(p["id"] in maps for place in places.values() for p in place["points"])


class Canvas:
    def __init__(self):
        self.lines = []
        self.labels = []

    def delete(self, *args):
        self.lines.clear()
        self.labels.clear()

    def create_line(self, *args, **kwargs):
        self.lines.append(args)

    def create_oval(self, *args, **kwargs):
        pass

    def create_text(self, *args, **kwargs):
        self.labels.append(kwargs["text"])

    def configure(self, **kwargs):
        pass


def test_builder_views_contain_only_zones_or_member_maps_and_actual_links():
    data = json.loads(Path("projects/authored/world.json").read_text())
    maps = data.get("maps", data)
    viewer = LayoutEditor.__new__(LayoutEditor)
    viewer.editor = SimpleNamespace(maps=maps)
    viewer.canvas = Canvas()
    viewer.selected = None
    viewer.mode = SimpleNamespace(get=lambda: "Carte générale")
    viewer.zone = SimpleNamespace(get=lambda: "grotte_oublies")
    viewer.draw()
    assert set(viewer.nodes) == set(maps["clearing"]["logical_zones"])
    assert "cave_1" not in viewer.nodes
    assert "cave_2" not in viewer.nodes
    viewer.mode = SimpleNamespace(get=lambda: "Points du lieu")
    viewer.draw()
    assert set(viewer.nodes) == {"cave_1", "cave_2"}
    assert viewer.canvas.labels == [maps["cave_1"]["name"], maps["cave_2"]["name"]]
    maps["cave_1"]["exits"] = [g for g in maps["cave_1"]["exits"] if g.get("destination") != "cave_2"]
    maps["cave_2"]["exits"] = [g for g in maps["cave_2"]["exits"] if g.get("destination") != "cave_1"]
    viewer.draw()
    assert not viewer.canvas.lines
