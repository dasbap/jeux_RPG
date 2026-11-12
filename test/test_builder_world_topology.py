import json
import os
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys

from jeuxRPG.multiplayer.map_world_editor import world_metadata
from jeuxRPG.multiplayer.world_topology import compile_world


def sector(name, zone):
    return {"name": name, "zone_id": zone, "sites": [], "exits": [], "biome": "forest"}


def test_deleted_world_metadata_never_inherits_runtime_defaults():
    maps = {"clearing": sector("Île", "clearing")}
    streets, routes = world_metadata(maps, {"rosee": {}}, [{"id": "old_route"}])
    assert streets == {} and routes == []
    places, streets, routes, _, _, _, edges = compile_world(maps)
    assert set(places) == {"clearing"}
    assert streets == {} and routes == []
    assert edges == {"clearing": {}}


def test_shared_zone_is_a_group_not_a_passage():
    maps = {"clearing": sector("Île A", "islands"), "other": sector("Île B", "islands")}
    maps["clearing"]["logical_zones"] = {"islands": {"name": "Archipel"}}
    places, _, _, _, _, entries, edges = compile_world(maps)
    assert set(places) == {"islands"}
    assert entries == {"islands": "clearing"}
    assert "other" not in edges["clearing"]
    assert edges["other"] == {}
    assert "other" not in edges["islands"]


def test_builder_gates_own_direction_duration_and_arrival():
    maps = {key: sector(key, key) for key in ("clearing", "other")}
    maps["clearing"]["exits"] = [{
        "destination": "other", "entry": [4, 6], "travel_minutes": .5,
    }]
    *_, edges = compile_world(maps)
    assert edges["clearing"]["other"] == {"seconds": 30, "entry": [4, 6]}
    assert "clearing" not in edges["other"]
    maps["clearing"]["exits"] = []
    assert compile_world(maps)[-1]["clearing"] == {}


def test_removed_route_and_streets_disappear_without_fallback():
    maps = {key: sector(key, key) for key in ("clearing", "port")}
    maps["clearing"]["travel_routes"] = [{
        "id": "ferry", "name": "Bateau", "from": "clearing", "to": "port",
        "distance_km": .5, "bidirectional": False,
    }]
    maps["port"]["village_streets"] = {
        "square": "dock", "streets": [{"id": "alley", "name": "Quai", "buildings": ["shop"]}],
    }
    *_, edges = compile_world(maps)
    assert "ferry" in edges["clearing"] and "port" in edges["ferry"]
    assert "ferry" not in edges["port"]
    assert "shop" in edges["alley"]
    del maps["clearing"]["travel_routes"]
    del maps["port"]["village_streets"]
    *_, edges = compile_world(maps)
    assert not {"ferry", "dock", "alley", "shop"} & edges.keys()


def test_authored_departure_reaches_rosee_without_lisiere_for_every_process_order():
    root = Path(__file__).resolve().parents[1]
    code = '''
import json
from jeuxRPG.multiplayer import fields, tutorial, world
from jeuxRPG.multiplayer.service import GameError
known = set(world.PLACES)
assert world.path("clearing", "rosee", known) == ["forest", "rosee"]
assert world.path("forest", "rosee", known) == ["rosee"]
assert world.path("lisiere", "rosee", known) == ["rosee_lisiere", "rosee"]
assert world.path("hunt", "rosee", known) == ["lisiere", "rosee_lisiere", "rosee"]
assert world.path("clearing", "clearing_rosee", known) is None
assert world.walking_seconds("forest", "rosee") == 30
assert world.walking_seconds("rosee", "forest") == 30
assert "forest" not in world.graph(known).get("zone_lisiere", [])
p = tutorial.new_party([{"id":"p", "name":"Itinéraire", "class_name":"Knight"}])
fields.start(p,0)
p.update(position="lisiere", battle=None, mobs=[], mob=None, step="village")
p.pop("field_map",None)
tutorial.execute(p,"p","travel",{"destination":"cave_2"},0,GameError,lambda:1)
tutorial.execute(p,"p","travel",{"destination":"rosee"},1,GameError,lambda:1)
assert not any(point.startswith("cave_") for point in p["journey"])
assert p["transit"]["destination"] in ("lisiere","rosee_lisiere"), p["transit"]
for physical in (False, True):
    p = tutorial.new_party([{"id":"p", "name":"Durée", "class_name":"Knight"}])
    fields.start(p, 0)
    fields.enter(p, "rosee", [2,20], 0)
    p.update(mobs=[], mob=None)
    if physical:
        gate = next(g for g in fields.MAPS["rosee"]["exits"] if g.get("destination") == "forest")
        assert gate["world_exit"] is True
        fields.transition(p, gate, "p", 0)
        tutorial.continue_journey(p, 0, lambda:1, [])
        assert p["transit"] is None and p["journey"] == []
        assert p.get("field_map") is None and p["position"] == "rosee"
        tutorial.execute(p, "p", "travel", {"destination":"forest"}, 0, GameError, lambda:1)
    else:
        p.update(battle=None)
        p.pop("field_map", None)
        tutorial.execute(p, "p", "travel", {"destination":"foret_eveilles"}, 0, GameError, lambda:1)
    assert p["transit"]["total"] == 30
    for now in (0.3, 1, 2.99, 3):
        tutorial.continue_journey(p, now, lambda:1, [])
        assert p.get("field_map") is None, "Aucune arrivée pendant la première seconde réelle"
    while p.get("transit") and p["transit"]["ready_at"] < 30:
        tutorial.continue_journey(p, p["transit"]["ready_at"], lambda:1, [])
    tutorial.continue_journey(p, 29.999, lambda:1, [])
    assert p.get("field_map") is None, "La durée du Builder doit être entièrement écoulée"
    tutorial.continue_journey(p, 30, lambda:1, [])
    assert p["field_map"] == ("forest" if physical else "clearing")
for source in ("rosee", "forest", "clearing"):
    for gate in fields.MAPS[source]["exits"]:
        assert gate["world_exit"] is True
        p = tutorial.new_party([{"id":"p", "name":"Sortie", "class_name":"Knight"}])
        fields.start(p, 0)
        fields.enter(p, source, gate["position"], 0)
        p.update(journey=["rosee"], transit=None)
        fields.transition(p, gate, "p", 0)
        tutorial.advance(p, 1000, lambda:1)
        assert p["position"] == source
        assert p.get("field_map") is None and p["battle"] is None
        assert p["transit"] is None and p["journey"] == []
        tutorial.execute(p,"p","enter_zone",{},1001,GameError,lambda:1)
        assert p["field_map"] == source
        assert p["battle"]["players"]["p"]["position"] == p["field_return_entry"]
legacy = {"position":"clearing_rosee", "transit":{"source":"clearing", "destination":"clearing_rosee"}, "journey":["rosee"], "visited":["clearing", "deleted_zone"]}
world.migrate_journey(legacy)
assert legacy["position"] == "clearing"
assert legacy["transit"] is None and legacy["journey"] == []
assert legacy["visited"] == ["clearing"]
assert "clearing_rosee" not in world.ROAD_POINTS
for target in ("rosee", "zone_rosee"):
    p = tutorial.new_party([{"id":"p", "name":"Audit", "class_name":"Knight"}])
    fields.start(p, 0)
    p.update(mobs=[], mob=None)
    gate = next(g for g in fields.MAPS["clearing"]["exits"] if not g.get("destination"))
    fields.transition(p, gate, "p", 0)
    tutorial.execute(p, "p", "travel", {"destination":target, "paths":{"clearing":["forest","rosee"]}}, 0, GameError, lambda:1)
    assert p["position"] == "forest", p["position"]
    assert p["transit"]["source"] == "forest"
    assert p["transit"]["destination"] == "rosee"
    assert p["transit"]["remaining"] == 30
    assert p["transit"]["field_entry"] == [2,20]
    for _ in range(8):
        if not p.get("transit"): break
        tutorial.continue_journey(p, p["transit"]["ready_at"], lambda:1, [])
    assert p["field_map"] == "rosee"
    assert p["battle"]["players"]["p"]["position"] == [2,20]
print(json.dumps(world.graph(known), sort_keys=True))
'''
    results = []
    for seed in ("0", "1", "2", "3"):
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=root,
            env={**os.environ, "RPG_MAPS_FILE": str(root / "projects/authored"), "PYTHONHASHSEED": seed},
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(json.loads(result.stdout))
    assert all(graph == results[0] for graph in results)


def test_delivered_world_matches_builder_project():
    root = Path(__file__).resolve().parents[1]
    authored = json.loads((root / "projects/authored/world.json").read_text(encoding="utf-8"))
    delivered = json.loads((root / "jeuxRPG/maps/world.json").read_text(encoding="utf-8"))
    assert authored == delivered


def test_builder_widgets_save_reopen_and_export_current_topology(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    from jeuxRPG.catalog_paths import CATALOG_NAMES
    from jeuxRPG.multiplayer import map_editor, map_building
    from jeuxRPG.multiplayer.controller_project import Project
    from jeuxRPG.multiplayer.map_layout_editor import LayoutEditor
    from jeuxRPG.multiplayer.map_world_editor import WorldEditor

    source = Path(__file__).resolve().parents[1] / "projects/authored"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    for name in CATALOG_NAMES:
        shutil.copyfile(source / name, project_dir / name)
    project = Project(project_dir)
    monkeypatch.setattr(map_building, "MOBS", project.mobs)
    monkeypatch.setattr(map_editor, "MOBS", project.mobs)
    for name, module in (("tk", tk), ("ttk", ttk), ("filedialog", filedialog),
                         ("messagebox", messagebox), ("simpledialog", simpledialog)):
        monkeypatch.setattr(map_editor, name, module, raising=False)
    root = tk.Tk()
    root.withdraw()
    try:
        editor = map_editor.MapEditor(root, project_dir / "world.json")

        def fail_dialog(title, message, **kwargs):
            raise AssertionError(f"{title}: {message}")

        monkeypatch.setattr(editor.messages, "showerror", fail_dialog)
        layout = LayoutEditor(editor)
        layout.mode.set("Carte générale")
        layout.draw()
        assert set(layout.nodes) == set(compile_world(editor.maps)[0])
        layout.selected = "zone_rosee"
        monkeypatch.setattr(editor, "form", lambda *args: {"name": "Rosée vérifiée"})
        layout.rename()
        assert layout.nodes["zone_rosee"][2] == "Rosée vérifiée"
        layout.panel.destroy()

        roads = WorldEditor(editor)
        index = next(i for i, route in enumerate(roads.routes) if route["id"] == "rosee_lisiere")
        roads.roads.selection_set(index)
        roads.delete_road()
        roads.apply()
        assert roads.panel.closed
        project.maps = deepcopy(editor.maps)
        project.save()

        reopened = Project(project_dir)
        topology = compile_world(reopened.maps)
        assert topology[0]["zone_rosee"]["name"] == "Rosée vérifiée"
        assert "rosee_lisiere" not in {route["id"] for route in topology[2]}
        assert topology[-1]["forest"]["rosee"]["seconds"] == 30
        exported = Project(tmp_path / "exported")
        exported.restore(reopened.state())
        exported.save()
        assert Project(exported.directory).maps == reopened.maps
    finally:
        root.destroy()
