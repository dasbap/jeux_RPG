"""Author the local Rosée expansion. Run explicitly, never during game startup."""

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jeuxRPG.multiplayer.controller_project import Project  # noqa: E402
from jeuxRPG.multiplayer.entity_sprite_art import populate  # noqa: E402
from jeuxRPG.multiplayer.living_world_catalog import build_catalog, fingerprint  # noqa: E402


def room(key, name, zone, width=48, height=32, biome="village", level=1):
    return {
        "id": f"field_{key}",
        "name": name,
        "zone_id": zone,
        "width": width,
        "height": height,
        "cell_metres": 2,
        "biome": biome,
        "level": level,
        "terrain_version": 2,
        "cover": [],
        "blocked": [],
        "water": [],
        "bridges": [],
        "paths": [],
        "decorations": [],
        "sites": [],
        "spawns": [],
        "spawners": [],
        "exits": [],
    }


def link(maps, source, point, target, entry):
    identifier = f"rosee_expansion_{source}_{target}"
    for a, b, exit_point, arrival in (
        (source, target, point, entry),
        (target, source, entry, point),
    ):
        # Arrive one tile inside, never on the reverse exit itself.
        width, height = maps[b]["width"], maps[b]["height"]
        inside = [
            max(1, min(width - 2, arrival[0])),
            max(1, min(height - 2, arrival[1])),
        ]
        maps[a]["exits"].append(
            {
                "position": exit_point[:],
                "destination": b,
                "entry": inside,
                "name": maps[b]["name"],
                "link_id": identifier,
                "travel_minutes": 0,
            }
        )


def decor(data, point, kind, solid=True):
    data["decorations"].append({"position": list(point), "kind": kind})
    if solid:
        data["cover"].append(list(point))


def building(data, x, y, width, height):
    # One contiguous roof, rather than a miniature house on every occupied tile.
    for py in range(y, y + height):
        for px in range(x, x + width):
            decor(data, [px, py], "roof")


def furnish(data, houses=()):
    width, height = data["width"], data["height"]
    for args in houses:
        building(data, *args)
    for y in range(height):
        for x in range(width):
            if abs(x - width // 2) <= 1 or abs(y - height // 2) <= 1:
                data["paths"].append([x, y])


def fortify(data):
    width, height = data["width"], data["height"]
    gates = [gate["position"] for gate in data["exits"]]
    for x in range(width):
        for y in (0, height - 1):
            if not any(abs(x - gx) <= 1 and y == gy for gx, gy in gates):
                decor(data, [x, y], "wall")
    for y in range(1, height - 1):
        for x in (0, width - 1):
            if not any(abs(y - gy) <= 1 and x == gx for gx, gy in gates):
                decor(data, [x, y], "wall")


def wilderness(data, kind):
    width, height = data["width"], data["height"]
    for y in range(2, height - 2):
        for x in range(2, width - 2):
            if abs(x - width // 2) < 3 or abs(y - height // 2) < 3:
                data["paths"].append([x, y])
            elif (x * 17 + y * 11) % 19 in (0, 1, 2):
                decor(data, [x, y], kind)
    for point in ([8, 8], [width - 9, height - 9]):
        data["spawns"].append(point)
        data["spawners"].append(
            {
                "position": point,
                "mob_id": "loup_gris" if kind == "tree" else "kobold_mineur",
                "level": data["level"],
                "count": 1,
            }
        )
        data["cover"] = [p for p in data["cover"] if p != point]
        data["decorations"] = [d for d in data["decorations"] if d["position"] != point]


def landscape(maps):
    town = maps["rosee"]
    for house in (
        (7, 35, 9, 7),
        (10, 45, 10, 6),
        (25, 7, 10, 6),
        (51, 7, 11, 6),
        (70, 35, 10, 7),
        (54, 46, 10, 5),
        (72, 46, 10, 5),
        (7, 17, 9, 6),
    ):
        building(town, *house)
    reserved = {tuple(p) for p in town["cover"]}
    roads = set(map(tuple, town["paths"]))
    for y in range(17, 32):
        for x in range(27, 63):
            roads.add((x, y))
    for y in (15, 33, 44):
        roads.update((x, y) for x in range(4, 84))
    for x in (23, 49, 66):
        roads.update((x, y) for y in range(3, 53))
    roads.update((70, y) for y in range(0, 29))
    town["paths"] = [list(p) for p in sorted(roads - reserved)]
    for x, y in (
        (5, 5),
        (40, 7),
        (82, 8),
        (5, 31),
        (40, 48),
        (82, 50),
        (20, 26),
        (66, 39),
    ):
        if (x, y) not in reserved:
            decor(town, [x, y], "tree")
    for x, y in ((22, 7), (36, 8), (65, 9), (5, 39), (21, 47), (67, 49), (82, 36)):
        decor(town, [x, y], "flowers", False)
    for key in ("rosee_marche", "rosee_habitations", "rosee_caserne"):
        data = maps[key]
        for x, y in ((19, 6), (28, 7), (4, 25), (43, 25)):
            decor(data, [x, y], "flowers", False)
    for x in (10, 16, 32, 38):
        decor(maps["rosee_caserne"], [x, 20], "rack", False)


def expand(project):
    maps = project.maps
    if maps["rosee"].get("rosee_expansion"):
        raise ValueError(
            "Extension déjà installée : modifier les cartes dans le Builder."
        )
    old_hash = fingerprint(build_catalog())
    original = deepcopy(maps["rosee"])
    zones = maps["clearing"]["logical_zones"]
    zones["forets_rosee"] = {
        "name": "Forêts et vergers de Rosée",
        "level": 2,
        "world_view": {"position": [330, 440]},
    }
    zones["monts_rosee"] = {
        "name": "Monts de Rosée",
        "level": 4,
        "world_view": {"position": [640, 70]},
    }
    for key in ("forest", "rosee_prairies", "rosee_verger", "rosee_bois"):
        maps[key]["zone_id"] = "forets_rosee"
    maps["rosee_carriere"]["zone_id"] = "monts_rosee"
    for quest in project.content["quests"]:
        if quest.get("zone") == "zone_rosee":
            quest["zone"] = (
                "monts_rosee"
                if quest["target"] == "gardien_de_schiste"
                else "forets_rosee"
            )
    additions = [
        ("rosee", "Rosée · place et portes", 88, 56),
        ("rosee_marche", "Rosée · quartier des artisans", 48, 32),
        ("rosee_habitations", "Rosée · quartier des maisons", 48, 32),
        ("rosee_caserne", "Rosée · cour de la caserne", 48, 32),
        ("rosee_dortoir", "Rosée · maison des gardes", 28, 20),
        ("rosee_armurerie", "Rosée · armurerie des chevaliers", 28, 20),
        ("rosee_remparts", "Rosée · remparts et porte du Nord", 48, 24),
    ]
    for index, (key, name, width, height) in enumerate(additions):
        maps[key] = room(key, name, "zone_rosee", width, height)
        maps[key]["settlement"] = "rosee"
        maps[key]["world_origin"] = [155 + (index % 3) * 95, 52 + (index // 3) * 70]
        maps[key]["world_view"] = {
            "position": [450 + (index % 3) * 220, 180 + (index // 3) * 180]
        }
    maps["rosee"].update(
        sites=original["sites"], rosee_expansion=1, world_view=original["world_view"]
    )
    extra = [
        ("rosee_clairiere", "Clairière des Sentinelles", "forets_rosee", "forest", 2),
        ("rosee_ruisseau", "Bois du Ruisseau", "forets_rosee", "forest", 3),
        ("rosee_contreforts", "Contreforts de Rosée", "monts_rosee", "mountain", 4),
        ("rosee_col", "Col des Guetteurs", "monts_rosee", "mountain", 5),
        ("rosee_tour", "Tour des Cimes", "monts_rosee", "mountain", 5),
    ]
    for index, (key, name, zone, biome, level) in enumerate(extra):
        maps[key] = room(key, name, zone, 48, 32, biome, level)
        maps[key]["world_origin"] = [80 + index * 65, -70]
        maps[key]["world_view"] = {"position": [160 + index * 210, 420]}
        wilderness(maps[key], "tree" if biome == "forest" else "rock")
    # Preserve the outside forest's existing access to the starting area.
    maps["forest"]["exits"] = [
        gate for gate in maps["forest"]["exits"] if gate.get("destination") != "rosee"
    ]
    maps["rosee_prairies"]["exits"] = [
        gate
        for gate in maps["rosee_prairies"]["exits"]
        if gate.get("destination") != "rosee"
    ]
    links = [
        ("rosee", [0, 28], "forest", [39, 13]),
        ("rosee", [87, 28], "rosee_marche", [0, 16]),
        ("rosee", [44, 55], "rosee_habitations", [24, 0]),
        ("rosee", [44, 0], "rosee_caserne", [24, 31]),
        ("rosee", [70, 0], "rosee_remparts", [0, 12]),
        ("rosee_marche", [47, 16], "rosee_prairies", [0, 12]),
        ("rosee_caserne", [0, 16], "rosee_dortoir", [27, 10]),
        ("rosee_caserne", [47, 16], "rosee_armurerie", [0, 10]),
        ("rosee_caserne", [24, 0], "rosee_remparts", [24, 23]),
        ("rosee_remparts", [24, 0], "rosee_contreforts", [24, 31]),
        ("forest", [20, 0], "rosee_clairiere", [24, 31]),
        ("rosee_clairiere", [47, 16], "rosee_ruisseau", [0, 16]),
        ("rosee_ruisseau", [47, 16], "rosee_bois", [20, 0]),
        ("rosee_contreforts", [47, 16], "rosee_carriere", [20, 0]),
        ("rosee_contreforts", [24, 0], "rosee_col", [24, 31]),
        ("rosee_col", [47, 16], "rosee_tour", [0, 16]),
        ("rosee_col", [24, 0], "lisiere", [20, 0]),
        ("rosee_habitations", [24, 31], "brume", [24, 0]),
    ]
    for args in links:
        link(maps, *args)
    # Clear approach corridors in existing wilderness maps.
    for key in ("forest", "rosee_bois", "rosee_carriere", "lisiere", "brume"):
        data = maps[key]
        for gate in data["exits"]:
            if not gate.get("link_id", "").startswith("rosee_expansion_"):
                continue
            x, y = gate["position"]
            corridor = (
                [[x, py] for py in range(0, data["height"] // 2 + 1)]
                if y == 0
                else [[px, y] for px in range(x, data["width"])]
            )
            for field in ("cover", "blocked", "water"):
                data[field] = [p for p in data.get(field, []) if p not in corridor]
            data["decorations"] = [
                d for d in data["decorations"] if d["position"] not in corridor
            ]
            data["paths"].extend(p for p in corridor if p not in data["paths"])
    furnish(
        maps["rosee"],
        [(12, 7, 9, 6), (25, 35, 10, 7), (54, 37, 10, 7), (69, 10, 10, 7)],
    )
    furnish(
        maps["rosee_marche"],
        [(7, 5, 9, 6), (30, 5, 10, 6), (7, 23, 9, 5), (32, 23, 10, 5)],
    )
    furnish(
        maps["rosee_habitations"],
        [(7, 5, 9, 6), (31, 5, 9, 6), (7, 23, 9, 5), (31, 23, 9, 5)],
    )
    furnish(
        maps["rosee_caserne"],
        [(7, 5, 9, 6), (31, 5, 10, 6), (7, 23, 9, 5), (32, 23, 10, 5)],
    )
    for key in ("rosee_dortoir", "rosee_armurerie", "rosee_remparts"):
        furnish(maps[key])
    for key, _, _, _ in additions:
        fortify(maps[key])
    maps["rosee_caserne"]["sites"] = [
        {
            "id": "capitaine_rosee",
            "name": "Avel · capitaine de la garde",
            "position": [24, 12],
            "dialogue": "Les chevaliers tiennent les portes. Les archers couvrent la cour et les remparts. Au siège, personne ne quitte son poste.",
        }
    ]
    maps["rosee_dortoir"]["sites"] = [
        {
            "id": "intendant_rosee",
            "name": "Loris · intendant des gardes",
            "position": [14, 8],
            "dialogue": "Voici la maison des gardes : relève, repos et rassemblement. La porte ouest de la cour mène ici.",
        }
    ]
    maps["rosee_armurerie"]["sites"] = [
        {
            "id": "armurier_rosee",
            "name": "Maëlle · armurière",
            "position": [14, 8],
            "dialogue": "Les arcs pour les guetteurs, les boucliers pour les chevaliers. Garrik reste à la place pour les commandes des voyageurs.",
        }
    ]
    maps["rosee_remparts"]["sites"] = [
        {
            "id": "guetteur_rosee",
            "name": "Félan · guetteur du Nord",
            "position": [20, 12],
            "dialogue": "Le chemin du nord traverse les contreforts, puis le col. À l'est, la carrière ; au-delà du col, la lisière.",
        }
    ]
    for key in ("rosee_dortoir", "rosee_armurerie"):
        for x in (5, 10, 18, 23):
            decor(maps[key], [x, 4], "bed" if key == "rosee_dortoir" else "rack", False)
    landscape(maps)
    # Explicitly supported predecessor; geography migration preserves raid/economy state.
    maps["clearing"]["previous_world_catalogs"] = [old_hash]
    populate(project)
    project.validate()


if __name__ == "__main__":
    project = Project(ROOT / "projects/authored")
    expand(project)
    project.save()
    print(f"Extension Rosée enregistrée : {len(project.maps)} cartes.")
