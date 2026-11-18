"""Deterministic, editable landscapes with a connected walkable area."""

import random
import re
from collections import deque


def _validate_settings(identifier, name, width, height, biome, density):
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[a-z0-9_]{1,64}", identifier
    ):
        raise ValueError(
            "Identifiant : minuscules, chiffres et underscores (64 maximum)."
        )
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Nom : 1 à 100 caractères.")
    if any(type(n) is not int or not 8 <= n <= 128 for n in (width, height)):
        raise ValueError("Dimensions : 8 à 128 cases.")
    if biome not in ("forest", "village", "cave"):
        raise ValueError("Ambiance : forest, village ou cave.")
    if type(density) is not int or not 0 <= density <= 60:
        raise ValueError("Densité : 0 à 60 %.")


def generate_map(
    identifier, name, width=30, height=20, biome="forest", seed="", density=25
):
    _validate_settings(identifier, name, width, height, biome, density)
    rng = random.Random(str(seed))
    midx, midy = width // 2, height // 2
    paths = {(x, midy) for x in range(width)} | {(midx, y) for y in range(height)}
    # Reserve a three-cell-wide cross, including the arrival beside each gate.
    reserved = {
        (x, y)
        for x in range(width)
        for y in range(height)
        if abs(x - midx) <= 1 or abs(y - midy) <= 1
    }
    water, bridges, cover, decorations = set(), set(), set(), {}
    if biome == "forest":
        river = max(2, width // 3)
        for y in range(height):
            for x in (river, river + 1):
                water.add((x, y))
                if abs(y - midy) <= 1:
                    bridges.add((x, y))
    for y in range(height):
        for x in range(width):
            point = (x, y)
            if point in reserved or point in water:
                continue
            edge = x in (0, width - 1) or y in (0, height - 1)
            chance = density / 100
            # Coarse clusters make groves and rocky ridges instead of uniform noise.
            chance *= 1.5 if (x // 4 + y // 4) % 2 else 0.5
            if (biome == "cave" and edge) or rng.random() < chance:
                kind = (
                    "rock"
                    if biome == "cave"
                    else "house"
                    if biome == "village"
                    else "tree"
                )
                if biome == "forest" and rng.random() < 0.22:
                    kind = "rock"
                cover.add(point)
                decorations[point] = kind
            elif rng.random() < 0.10:
                decorations[point] = (
                    "crystal"
                    if biome == "cave"
                    else "flowers"
                    if biome == "village"
                    else "grass"
                )
    blocked = water - bridges
    # Remove isolated pockets: every remaining walkable cell reaches all four gates.
    obstacles = cover | blocked
    reachable, queue = {(0, midy)}, deque([(0, midy)])
    while queue:
        x, y = queue.popleft()
        for p in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= p[0] < width
                and 0 <= p[1] < height
                and p not in obstacles
                and p not in reachable
            ):
                reachable.add(p)
                queue.append(p)
    for y in range(height):
        for x in range(width):
            p = (x, y)
            if p not in reachable and p not in blocked and p not in cover:
                cover.add(p)
                decorations[p] = "rock" if biome == "cave" else "tree"

    def cells(points):
        return [list(p) for p in sorted(points, key=lambda p: (p[1], p[0]))]

    return {
        "id": "field_" + identifier,
        "name": name.strip(),
        "width": width,
        "height": height,
        "cell_metres": 2,
        "biome": biome,
        "cover": cells(cover),
        "blocked": cells(blocked),
        "water": cells(water),
        "bridges": cells(bridges),
        "paths": cells(paths),
        "decorations": [
            {"position": list(p), "kind": kind}
            for p, kind in sorted(decorations.items())
        ],
        "spawns": [],
        "spawners": [],
        "sites": [],
        "zone_level": 1,
        "exits": [
            {
                "position": list(p),
                "destination": None,
                "entry": None,
                "name": "Chemins rapides",
            }
            for p in ((0, midy), (width - 1, midy), (midx, 0), (midx, height - 1))
        ],
    }
