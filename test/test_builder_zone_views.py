import json
from pathlib import Path
from types import SimpleNamespace

from world_checks import assert_connected_world, zone_members

from jeuxRPG.multiplayer.map_layout_editor import LayoutEditor, layout_places


def test_local_and_packaged_world_group_every_map_into_its_authored_zone():
    for path in ("projects/authored/world.json", "jeuxRPG/maps/world.json"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        maps = data.get("maps", data)
        assert_connected_world(maps)
        places = layout_places(maps)
        expected = zone_members(maps)
        assert set(places) == set(expected)
        for zone, members in expected.items():
            assert {point["id"] for point in places[zone]["points"]} == members
        points = [point["id"] for place in places.values() for point in place["points"]]
        assert len(points) == len(set(points)) == len(maps)
        assert set(points) == set(maps)


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
    data = json.loads(Path("projects/authored/world.json").read_text(encoding="utf-8"))
    maps = data.get("maps", data)
    viewer = LayoutEditor.__new__(LayoutEditor)
    viewer.editor = SimpleNamespace(maps=maps)
    viewer.canvas = Canvas()
    viewer.selected = None
    viewer.mode = SimpleNamespace(get=lambda: "Carte générale")
    viewer.zone = SimpleNamespace(get=lambda: None)
    viewer.draw()
    expected = zone_members(maps)
    assert set(viewer.nodes) == set(expected)
    viewer.mode = SimpleNamespace(get=lambda: "Points du lieu")
    for zone, members in expected.items():
        viewer.zone = SimpleNamespace(get=lambda zone=zone: zone)
        viewer.draw()
        assert set(viewer.nodes) == members
        assert set(viewer.canvas.labels) == {
            point["name"] for point in layout_places(maps)[zone]["points"]
        }
        edges = [
            (key, gate["destination"])
            for key in members
            for gate in maps[key]["exits"]
            if gate.get("destination") in members and gate["destination"] != key
        ]
        assert len(viewer.canvas.lines) == len(edges)
        original = {key: maps[key]["exits"] for key in members}
        for key in members:
            maps[key]["exits"] = [
                g for g in maps[key]["exits"] if g.get("destination") not in members
            ]
        viewer.draw()
        assert not viewer.canvas.lines
        for key in members:
            maps[key]["exits"] = original[key]
