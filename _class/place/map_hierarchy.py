"""Map hierarchy system.

Provides:
- Static hierarchy: Dimension > Continent > Kingdom > Town (from JSON)
- Place-based "world" graph: Town objects + travel links (no coordinate system)
"""
import json
from pathlib import Path
from typing import Optional, Dict, List

from jeuxRPG._class.place.town import Town

class MapLevel:
    def __init__(self, name: str, level_type: str, size: Optional[tuple]=None, parent=None):
        self.name = name
        self.level_type = level_type  # 'dimension', 'continent', 'kingdom', 'town'
        self.size = size  # (width, height)
        self.parent = parent
        self.children: List[MapLevel] = []

    def add_child(self, child: 'MapLevel'):
        self.children.append(child)
        child.parent = self

    def get_full_path(self) -> List[str]:
        node = self
        path = []
        while node:
            path.append(node.name)
            node = node.parent
        return list(reversed(path))

    def __repr__(self):
        return f"<{self.level_type.capitalize()}: {self.name} ({self.size})>"


def load_map_hierarchy(structure_path: str, towns_data: Dict[str, Dict]) -> MapLevel:
    """
    Load the map hierarchy from structure.json and towns.json.
    Returns the root MapLevel (dimension).
    """
    with open(structure_path, encoding="utf-8") as f:
        struct = json.load(f)
    dim = struct["dimensions"][0]
    root = MapLevel(dim["name"], "dimension")
    for cont in dim["continents"]:
        cont_node = MapLevel(cont["name"], "continent")
        root.add_child(cont_node)
        for kingdom in cont["kingdoms"]:
            king_node = MapLevel(kingdom["name"], "kingdom")
            cont_node.add_child(king_node)
            for town_name in kingdom["towns"]:
                town_info = towns_data.get(town_name, {})
                size = town_info.get("size", (30, 20))
                town_node = MapLevel(town_name, "town", size=size)
                king_node.add_child(town_node)
    return root


def get_towns_data(towns_path: str) -> Dict[str, Dict]:
    with open(towns_path, encoding="utf-8") as f:
        data = json.load(f)
    return {t["name"]: t for t in data["towns"]}


_town_graph_cache: dict[str, Town] | None = None
_town_graph_cache_path: str | None = None


def load_town_graph(towns_path: str) -> dict[str, Town]:
    """Load a place-based town graph from towns.json.

    This intentionally ignores any x/y fields (coordinate system removed) and
    only builds Town objects + travel connections from the "paths" section.
    """
    with open(towns_path, encoding="utf-8") as f:
        data = json.load(f)

    towns: dict[str, Town] = {}
    for t in data.get("towns", []):
        name = str(t.get("name", "")).strip()
        if not name:
            continue
        town = Town(
            name=name,
            population=int(t.get("population", 0) or 0),
            wealth=int(t.get("wealth", 0) or 0),
            reputation=int(t.get("reputation", 0) or 0),
        )
        # Keep optional size metadata (dimensions) without enabling coords.
        size = t.get("size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                town.size = (int(size[0]), int(size[1]))
            except Exception:
                town.size = None
        # Store optional metadata without enforcing a coordinate system.
        town.entry_points = list(t.get("entry_points", []) or [])
        town.pois = list(t.get("buildings", []) or [])

        # Ensure the town has an entry district so Navigator can spawn.
        if not town.districts:
            town.create_district("Centre")
            town.set_entry_district("Centre")

        towns[name] = town

    for p in data.get("paths", []) or []:
        a_name = str(p.get("from", "")).strip()
        b_name = str(p.get("to", "")).strip()
        if not a_name or not b_name:
            continue
        a = towns.get(a_name)
        b = towns.get(b_name)
        if not a or not b:
            continue
        bidir = bool(p.get("bidirectional", True))
        a.connect_to(b, bidirectional=bidir)

    return towns


def get_town_graph(towns_path: str) -> dict[str, Town]:
    """Return cached town graph for a towns.json path."""
    global _town_graph_cache, _town_graph_cache_path
    if _town_graph_cache is None or _town_graph_cache_path != towns_path:
        _town_graph_cache = load_town_graph(towns_path)
        _town_graph_cache_path = towns_path
    return _town_graph_cache
