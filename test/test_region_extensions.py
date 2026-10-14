import json
from collections import deque
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import map_building
from jeuxRPG.multiplayer.map_assets import validate

ROOT = Path(__file__).resolve().parents[1]


def reachable(definition, start):
    blocked = set(map(tuple, definition["cover"] + definition["blocked"]))
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
def test_region_extensions_are_connected_and_playable(prefix, monkeypatch):
    directory = ROOT / prefix
    world = json.loads((directory / "world.json").read_text())
    mobs = json.loads((directory / "mobs.json").read_text())["maps"]
    monkeypatch.setattr(map_building, "MOBS", mobs)
    validate(world)
    added = {
        key: definition
        for key, definition in world.items()
        if key.startswith(("rosee_", "brume_"))
    }
    assert len(added) == 8
    levels = {"zone_rosee": set(), "zone_brume": set()}
    seen = {"rosee", "brume"}
    queue = deque(seen)
    while queue:
        key = queue.popleft()
        for exit in world[key]["exits"]:
            target = exit.get("destination")
            if target and target not in seen:
                seen.add(target)
                queue.append(target)
    assert set(added) <= seen
    for key, definition in added.items():
        accessible = reachable(definition, definition["exits"][0]["position"])
        for exit in definition["exits"]:
            assert tuple(exit["position"]) in accessible
            target = world[exit["destination"]]
            assert any(
                back.get("destination") == key
                and back.get("link_id") == exit["link_id"]
                for back in target["exits"]
            )
            back = next(
                back
                for back in target["exits"]
                if back.get("link_id") == exit["link_id"]
            )
            assert tuple(back["position"]) in reachable(target, exit["entry"])
        for spawn in definition["spawners"]:
            assert tuple(spawn["position"]) in accessible
            assert all(tuple(point) in accessible for point in spawn["patrol"])
            actor = map_building.create_mob(world, key, spawn, 0)
            assert actor["level"] == spawn["level"]
            levels[definition["zone_id"]].add(actor["level"])
    assert levels["zone_rosee"] <= set(range(1, 6))
    assert levels["zone_brume"] == set(range(1, 11))
    assert not world["rosee"]["spawns"]
    assert not world["brume"]["spawns"]
