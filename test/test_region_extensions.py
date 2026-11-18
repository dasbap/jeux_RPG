import json
from collections import deque
from pathlib import Path

import pytest
from world_checks import assert_connected_world

from jeuxRPG.multiplayer import map_building
from jeuxRPG.multiplayer.map_assets import validate
from jeuxRPG.multiplayer.map_playability import issues

ROOT = Path(__file__).resolve().parents[1]


def reachable(definition, start):
    blocked = set(map(tuple, definition["cover"] + definition["blocked"]))
    blocked.update(
        tuple(point)
        for point in definition.get("water", [])
        if point not in definition.get("bridges", [])
    )
    seen = {tuple(start)}
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for point in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if (
                0 <= point[0] < definition["width"]
                and 0 <= point[1] < definition["height"]
                and point not in blocked
                and point not in seen
            ):
                seen.add(point)
                queue.append(point)
    return seen


@pytest.mark.parametrize("prefix", ["jeuxRPG/maps", "projects/authored"])
def test_all_authored_maps_are_connected_and_playable(prefix, monkeypatch):
    directory = ROOT / prefix
    world = json.loads((directory / "world.json").read_text(encoding="utf-8"))
    mobs = json.loads((directory / "mobs.json").read_text(encoding="utf-8"))["maps"]
    monkeypatch.setattr(map_building, "MOBS", mobs)
    validate(world)
    assert_connected_world(world)
    assert not issues(world)
    for key, definition in world.items():
        accessible = reachable(definition, definition["exits"][0]["position"])
        for exit in definition["exits"]:
            assert tuple(exit["position"]) in accessible
        for spawn in map_building.spawners(definition):
            assert tuple(spawn["position"]) in accessible
            assert all(tuple(point) in accessible for point in spawn.get("patrol", []))
            actor = map_building.create_mob(world, key, spawn, 0)
            assert 1 <= actor["level"] <= 100
            if spawn.get("level") is not None:
                assert actor["level"] == spawn["level"]
    assert not world["rosee"]["spawns"]
    assert not world["brume"]["spawns"]
