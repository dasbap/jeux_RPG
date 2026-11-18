from collections import deque
from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeuxRPG.multiplayer import fields, map_assets
from jeuxRPG.multiplayer.map_editor import MapEditor
from jeuxRPG.multiplayer.map_generator import generate_map


@pytest.mark.parametrize("biome", ["forest", "village", "cave"])
@pytest.mark.parametrize("size,density", [(8, 0), (8, 60), (30, 25), (128, 60)])
def test_generated_landscape_is_valid_and_all_walkable_cells_are_connected(
    biome, size, density
):
    data = generate_map("generated", "Région test", size, size, biome, "test", density)
    maps = {**fields.MAPS, "generated": data}
    map_assets.validate(maps)
    obstacles = {tuple(p) for p in data["cover"] + data["blocked"]}
    start = tuple(data["exits"][0]["position"])
    reached, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= p[0] < size
                and 0 <= p[1] < size
                and p not in obstacles
                and p not in reached
            ):
                reached.add(p)
                queue.append(p)
    assert len(reached) + len(obstacles) == size * size
    assert all(tuple(g["position"]) in reached for g in data["exits"])


def test_seed_replays_exactly_and_other_seeds_vary_the_landscape():
    assert generate_map("test", "Test", seed="rosee") == generate_map(
        "test", "Test", seed="rosee"
    )
    assert generate_map("test", "Test", seed="rosee") != generate_map(
        "test", "Test", seed="brume"
    )


@pytest.mark.parametrize(
    "options",
    [
        {"width": 7},
        {"height": 129},
        {"density": 61},
        {"biome": "unknown"},
        {"identifier": "../test"},
    ],
)
def test_invalid_generation_settings_are_rejected(options):
    with pytest.raises(ValueError):
        generate_map(**{"identifier": "test", "name": "Test", **options})


def test_builder_generation_is_undoable_and_never_overwrites_a_map():
    editor = MapEditor.__new__(MapEditor)
    editor.maps = deepcopy(fields.MAPS)
    original = deepcopy(editor.maps)
    editor.selected = SimpleNamespace(get=lambda: "clearing")
    editor.history = []
    editor.status = SimpleNamespace(set=lambda message: None)
    errors = []
    editor._messages = SimpleNamespace(showerror=lambda *args: errors.append(args))
    editor.show_map = lambda key: None
    editor.form = lambda *args: {
        "map_id": "generated",
        "name": "Test",
        "width": "30",
        "height": "20",
        "biome": "forest",
        "seed": "1",
        "density": "25",
        "zone_id": "clearing",
    }
    assert editor.generate() == "generated"
    assert len(editor.history) == 1
    assert editor.history[0] == original
    assert all(editor.maps[key] == value for key, value in original.items())
    snapshot = deepcopy(editor.maps)
    assert editor.generate() is None
    assert errors and editor.maps == snapshot and len(editor.history) == 1
