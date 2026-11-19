import json
from collections import deque
from copy import deepcopy
from pathlib import Path

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.map_playability import issues
from jeuxRPG.multiplayer.world_topology import compile_world
from scripts.refine_forgotten_cave import ROOMS, refine
from scripts.rework_world_maps import arrange

ROOT = Path(__file__).resolve().parents[1]


def test_labyrinth_is_connected_cyclic_playable_and_exported():
    authored = json.loads(
        (ROOT / "projects/authored/world.json").read_text(encoding="utf-8")
    )
    shipped = json.loads((ROOT / "jeuxRPG/maps/world.json").read_text(encoding="utf-8"))
    assert authored == shipped
    caves = {key: authored[key] for key in ROOMS}
    assert len(caves) >= 10
    assert not issues(caves)
    distance = {"cave_1": 0}
    queue = deque(distance)
    links = set()
    scrambled = 0
    for key, data in caves.items():
        assert data["biome"] == "cave"
        assert data["water"] and data["paths"]
        assert {"camp", "crystal"} <= {d["kind"] for d in data["decorations"]}
        assert all(10 <= s["level"] <= 15 for s in data["spawners"])
        for gate in data["exits"]:
            target = gate["destination"]
            if target not in caves:
                continue
            links.add(tuple(sorted((key, target))))
            reverse = next(g for g in caves[target]["exits"] if g["destination"] == key)
            assert gate["entry"] not in [g["position"] for g in caves[target]["exits"]]
            # A normal east-west or north-south connection would share a coordinate axis.
            source_vertical = gate["position"][1] in (0, data["height"] - 1)
            target_vertical = reverse["position"][1] in (0, caves[target]["height"] - 1)
            scrambled += source_vertical != target_vertical
    while queue:
        source = queue.popleft()
        for gate in caves[source]["exits"]:
            target = gate["destination"]
            if target in caves and target not in distance:
                distance[target] = distance[source] + 1
                queue.append(target)
    assert set(distance) == set(caves)
    assert len(links) - len(caves) + 1 >= 5
    assert distance["cave_2"] >= 5  # No direct shortcut from entrance to boss.
    assert scrambled >= 10
    assert caves["cave_2"]["dungeon"]["final"]
    assert caves["cave_2"]["spawners"][0]["mob_id"] == "gobelin_boss"
    assert caves["cave_2"]["spawners"][0]["level"] == 15
    assert {s["level"] for m in caves.values() for s in m["spawners"]} == set(
        range(10, 16)
    )
    routes = {r["id"]: r for r in authored["clearing"]["travel_routes"]}
    for route_id, map_id, point in (
        ("link_3516d81727964944", "cave_1", [0, 7]),
        ("link_b2f15f563af441e1", "cave_2", [31, 15]),
    ):
        assert routes[route_id]["from"] == map_id
        gate = next(g for g in caves[map_id]["exits"] if g["position"] == point)
        assert gate["destination"] == routes[route_id]["to"]
        assert not gate.get("world_exit")
        assert "from_entry" not in routes[route_id]


def test_authoring_is_repeatable_and_does_not_change_outdoor_gameplay():
    project = Project(ROOT / "projects/authored")
    before = deepcopy(project.maps)
    refine(project)
    arrange(project)
    first = deepcopy(project.maps)
    refine(project)
    arrange(project)
    assert project.maps == first
    for key, data in before.items():
        if key not in ROOMS:
            assert {
                k: v
                for k, v in data.items()
                if k not in ("world_view", "logical_zones", "travel_routes")
            } == {
                k: v
                for k, v in project.maps[key].items()
                if k not in ("world_view", "logical_zones", "travel_routes")
            }
    places, _, routes, levels, _, _, edges = compile_world(project.maps)
    assert levels["grotte_oublies"] == 10
    assert all(r["name"] != "Nouvelle route" for r in routes)
    for zone, place in places.items():
        positions = [(p["x"], p["y"]) for p in place["points"]]
        assert len(set(positions)) == len(positions), zone
        assert all(
            abs(x - tx) >= 80 or abs(y - ty) >= 70
            for i, (x, y) in enumerate(positions)
            for tx, ty in positions[i + 1 :]
        ), zone
    assert set(ROOMS) <= set(edges)


def test_global_roads_do_not_cross_outside_the_labyrinth():
    from itertools import combinations

    from jeuxRPG.multiplayer.map_building import zone_of
    from scripts.rework_world_maps import GLOBAL

    project = Project(ROOT / "projects/authored")
    roads = set()
    for source, data in project.maps.items():
        for gate in data.get("exits", []):
            if gate.get("destination") in project.maps:
                a, b = (
                    zone_of(project.maps, source),
                    zone_of(project.maps, gate["destination"]),
                )
                if a != b:
                    roads.add(tuple(sorted((a, b))))
    for route in project.maps["clearing"]["travel_routes"]:
        roads.add(
            tuple(
                sorted(
                    (
                        zone_of(project.maps, route["from"]),
                        zone_of(project.maps, route["to"]),
                    )
                )
            )
        )

    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    for (a, b), (c, d) in combinations(roads, 2):
        if len({a, b, c, d}) != 4:
            continue
        a, b, c, d = (GLOBAL[key] for key in (a, b, c, d))
        assert not (
            orientation(a, b, c) * orientation(a, b, d) < 0
            and orientation(c, d, a) * orientation(c, d, b) < 0
        )
