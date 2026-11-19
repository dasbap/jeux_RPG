"""Build the editable Forgotten Cave as a repeatable twelve-room labyrinth."""

from collections import deque
from copy import deepcopy
from random import Random

from jeuxRPG.multiplayer.controller_project import Project

ROOMS = ["cave_1", *[f"cave_{n}" for n in range(3, 13)], "cave_2"]
NAMES = [
    "Seuil des Oubliés",
    "Galerie des Retours",
    "Salle des Reflets",
    "Croisée sans Nord",
    "Chambre des Murmures",
    "Faille des Échos",
    "Rotonde Renversée",
    "Passage des Ombres",
    "Crypte des Égarés",
    "Antichambre Brisée",
    "Nœud des Profondeurs",
    "Trône de l'Oubli",
]
SPINE = [0, 5, 2, 8, 1, 7, 4, 10, 3, 9, 6, 11]
EDGES = list(zip(SPINE, SPINE[1:], strict=False)) + list(
    zip(SPINE, SPINE[2:], strict=False)
)


def refine(project):
    graph = {key: [] for key in ROOMS}
    for a, b in EDGES:
        graph[ROOMS[a]].append(ROOMS[b])
        graph[ROOMS[b]].append(ROOMS[a])
    distance = {ROOMS[0]: 0}
    pending = deque(distance)
    while pending:
        source = pending.popleft()
        for target in graph[source]:
            if target not in distance:
                distance[target] = distance[source] + 1
                pending.append(target)
    template = deepcopy(project.maps["cave_1"])
    ports = {}
    for index, key in enumerate(ROOMS):
        data = project.maps.setdefault(key, deepcopy(template))
        width, height = (
            (22, 16)
            if key == "cave_1"
            else (
                (44, 16)
                if key == "cave_2"
                else (28 + index % 3 * 4, 20 + index % 2 * 4)
            )
        )
        cx, cy = width // 2, (height - 1) // 2
        data.update(
            id=f"field_{key}",
            name=NAMES[index],
            width=width,
            height=height,
            biome="cave",
            zone_id="grotte_oublies",
            level=min(15, 10 + distance[key]),
            dungeon={
                "id": "grotte_gobeline",
                "room": index + 1,
                "final": key == "cave_2",
                "lock_until_clear": False,
            },
            sites=[],
            exits=[],
            world_view={},
            world_origin=[index * 80, -1000],
        )
        doors = [(0, cy), (width - 1, cy), (cx, 0), (cx, height - 1)]
        if key == "cave_1":
            doors.pop(0)
            data["exits"].append(
                {
                    "position": [0, 7],
                    "destination": None,
                    "entry": None,
                    "name": "Vers la Forêt des Éveillés",
                }
            )
        if key == "cave_2":
            doors.pop(3)
            data["exits"].append(
                {
                    "position": [31, 15],
                    "destination": None,
                    "entry": None,
                    "name": "Faille vers la Lisière",
                }
            )
        Random(821 + index).shuffle(doors)
        ports[key] = dict(zip(graph[key], doors, strict=False))
    for index, key in enumerate(ROOMS):
        data = project.maps[key]
        width, height = data["width"], data["height"]
        cx, cy = width // 2, (height - 1) // 2
        for target, door in ports[key].items():
            tx, ty = ports[target][key]
            destination = project.maps[target]
            arrival = [
                2
                if tx == 0
                else destination["width"] - 3
                if tx == destination["width"] - 1
                else tx,
                2
                if ty == 0
                else destination["height"] - 3
                if ty == destination["height"] - 1
                else ty,
            ]
            data["exits"].append(
                {
                    "position": list(door),
                    "destination": target,
                    "entry": arrival,
                    "name": f"Arche vers {destination['name']}",
                }
            )
        floor = {
            (x, y)
            for x in range(width)
            for y in range(height)
            if ((x - cx) / (width * 0.40)) ** 2 + ((y - cy) / (height * 0.32)) ** 2 <= 1
        }
        paths = set()
        for gate in data["exits"]:
            gx, gy = gate["position"]
            bend = (cx, gy) if index % 2 else (gx, cy)
            for (ax, ay), (bx, by) in (([gx, gy], bend), (bend, (cx, cy))):
                line = {
                    (x, y)
                    for x in range(min(ax, bx), max(ax, bx) + 1)
                    for y in range(min(ay, by), max(ay, by) + 1)
                }
                paths.update(line)
                floor.update(
                    (x + dx, y + dy)
                    for x, y in line
                    for dx in (-1, 0, 1)
                    for dy in (-1, 0, 1)
                    if 0 <= x + dx < width and 0 <= y + dy < height
                )
        spawns = [[cx - 3, cy - 2], [cx + 3, cy + 2], [cx, cy + 3]]
        if key == "cave_1":
            spawns = [[10, 6], [10, 9], [15, 7]]
        elif key == "cave_2":
            spawns = [[30, 7], [26, 9], [34, 6]]
            floor.update((x, y) for x in range(24, 39) for y in range(4, 12))
        safe = {
            (x + dx, y + dy)
            for x, y in spawns
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
        }
        floor.update(safe)
        water = {
            (cx - 4, cy - 3),
            (cx - 5, cy - 3),
            (cx + 4, cy - 3),
            (cx + 5, cy - 3),
        } & floor - paths - safe
        cover = {(x, y) for x in range(width) for y in range(height)} - floor
        monsters = ["gobelin_berserker", "gobelin_archer", "gobelin_chamane"]
        if index % 3 == 1:
            monsters = ["chauve_souris", "squelette_archer", "golem_de_pierre"]
        elif index % 3 == 2:
            monsters = ["scorpion_des_roches", "gobelin_archer", "liche_apprentie"]
        data.update(
            cover=[list(p) for p in sorted(cover)],
            paths=[list(p) for p in sorted(paths)],
            water=[list(p) for p in sorted(water)],
            blocked=[list(p) for p in sorted(water)],
            bridges=[],
            bridge_rotations=[],
            spawns=spawns,
            spawners=[
                {
                    "position": p,
                    "mob_id": "gobelin_boss"
                    if key == "cave_2" and n == 0
                    else monsters[n],
                    "level": data["level"],
                    "count": 1 if key == "cave_2" and n == 0 else 2,
                }
                for n, p in enumerate(spawns)
            ],
            decorations=[{"position": list(p), "kind": "rock"} for p in sorted(cover)]
            + [
                {"position": [x, y], "kind": kind}
                for kind, points in (
                    ("crystal", [(cx - 6, cy - 2), (cx + 6, cy - 2), (cx + 4, cy + 3)]),
                    ("camp", [(cx - 5, cy + 2), (cx + 5, cy + 2)]),
                )
                for x, y in points
                if (x, y) in floor - water
            ],
        )
    project.maps["clearing"]["logical_zones"]["grotte_oublies"].update(
        level=10,
        description="Douze salles entrelacées, arches trompeuses et ennemis de niveau 10 à 15.",
    )
    if any(
        r["id"] == "lisiere_cave_entrance"
        for r in project.maps["clearing"].get("travel_routes", [])
    ):
        from scripts.refine_lisiere import author as refine_lisiere

        refine_lisiere(project)
    project.validate()


if __name__ == "__main__":
    project = Project("projects/authored")
    refine(project)
    project.save()
    print("Forgotten Cave: twelve rooms, twenty-one passages, enemies level 10-15.")
