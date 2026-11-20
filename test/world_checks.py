"""Structural assertions for growing authored worlds, without a zone inventory."""

from collections import defaultdict

from jeuxRPG.multiplayer.map_building import zone_of
from jeuxRPG.multiplayer.world_topology import compile_world


def zone_members(maps):
    members = defaultdict(set)
    for key in maps:
        members[zone_of(maps, key)].add(key)
    return dict(members)


def assert_connected_world(maps, start="clearing"):
    assert start in maps, f"Missing starting map: {start}"
    for key, definition in maps.items():
        for gate in definition.get("exits", []):
            target = gate.get("destination")
            assert target is None or target in maps, f"Broken exit: {key} -> {target}"
    *_, edges = compile_world(maps)

    def reached(graph):
        visited, pending = set(), [start]
        while pending:
            point = pending.pop()
            if point not in visited:
                visited.add(point)
                pending.extend(graph.get(point, ()))
        return visited

    missing = set(maps) - reached(edges)
    assert not missing, f"Maps unreachable from {start}: {sorted(missing)}"
    reverse = defaultdict(set)
    for source, targets in edges.items():
        for target in targets:
            reverse[target].add(source)
    trapped = set(maps) - reached(reverse)
    assert not trapped, f"Maps without a return path to {start}: {sorted(trapped)}"
