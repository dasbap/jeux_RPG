import hashlib
import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path


def validate(maps):
    if not isinstance(maps, dict) or not maps or len(maps) > 100:
        raise ValueError("Le fichier doit contenir de 1 à 100 cartes.")
    if not {"clearing", "rosee", "lisiere", "hunt", "forest", "cave_1", "brume"} <= maps.keys():
        raise ValueError("Les cartes du tutoriel doivent être conservées.")
    maps = deepcopy(maps)
    owners = set(maps)
    for definition in maps.values():
        history = definition.get('previous_ids',[]) if isinstance(definition,dict) else []
        if not isinstance(history,list) or len(history) > 100 or any(not isinstance(key,str) or not re.fullmatch(r'[a-z0-9_]{1,64}',key) or key in owners for key in history) or len(set(history)) != len(history):
            raise ValueError('Historique de carte invalide ou identifiant réservé.')
        owners.update(history)
    for key, definition in maps.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", key) or not isinstance(definition, dict):
            raise ValueError("Identifiant de carte invalide.")
        from .map_layout_editor import validate_layout
        validate_layout(definition.get("world_view", {}))
        dungeon = definition.get("dungeon")
        if dungeon is not None:
            if not isinstance(dungeon, dict) or set(dungeon) != {"id", "room", "final", "lock_until_clear"} or not isinstance(dungeon.get("id"), str) or not re.fullmatch(r"[a-z0-9_]{1,64}", dungeon["id"]) or type(dungeon.get("room")) is not int or not 1 <= dungeon["room"] <= 100 or type(dungeon.get("final")) is not bool or type(dungeon.get("lock_until_clear")) is not bool:
                raise ValueError(f"{key} : métadonnées de donjon invalides.")
        for field in ("world_zone", "fast_travel_origin"):
            if field in definition and (not isinstance(definition[field], str) or definition[field] not in maps):
                raise ValueError(f"{key} : référence {field} invalide.")
        if "world_origin" in definition and (not isinstance(definition["world_origin"], list) or len(definition["world_origin"]) != 2 or any(type(n) is not int for n in definition["world_origin"])):
            raise ValueError(f"{key} : origine du secteur invalide.")
        metres = definition.get("cell_metres", 2)
        if type(metres) not in (int, float) or not .1 <= metres <= 100:
            raise ValueError(f"{key} : taille de case comprise entre 0.1 et 100 m.")
        width, height = definition.get("width"), definition.get("height")
        if type(width) is not int or type(height) is not int or not 4 <= width <= 128 or not 4 <= height <= 128:
            raise ValueError(f"{key} : dimensions comprises entre 4 et 128.")
        if definition.get("id") != "field_" + key or not isinstance(definition.get("name"), str) or not 1 <= len(definition["name"]) <= 100:
            raise ValueError(f"{key} : nom ou identifiant interne invalide.")
        def point(value):
            if not isinstance(value, list) or len(value) != 2 or any(type(n) is not int for n in value) or not 0 <= value[0] < width or not 0 <= value[1] < height:
                raise ValueError(f"{key} : case hors carte.")
        for field in ("cover", "blocked", "water", "bridges", "paths", "spawns"):
            values = definition.get(field, [])
            if not isinstance(values, list) or len(values) > width * height:
                raise ValueError(f"{key} : liste {field} invalide.")
            for value in values:
                point(value)
        rotations = definition.get("bridge_rotations", [])
        if not isinstance(rotations, list) or len(rotations) > width * height:
            raise ValueError(f"{key} : rotations de pont invalides.")
        seen_bridges = set()
        for item in rotations:
            if not isinstance(item, dict):
                raise ValueError(f"{key} : rotation de pont invalide.")
            point(item.get("position"))
            if item["position"] not in definition.get("bridges", []) or tuple(item["position"]) in seen_bridges or type(item.get("rotation")) is not int or item["rotation"] not in (0, 90, 180, 270):
                raise ValueError(f"{key} : pont absent, dupliqué ou rotation invalide.")
            seen_bridges.add(tuple(item["position"]))
        definition.setdefault("sites", [])
        definition.setdefault("spawns", [])
        definition.setdefault("cover", [])
        definition.setdefault("blocked", [])
        blocked = {tuple(p) for p in definition.get("cover", []) + definition.get("blocked", [])}
        if len({tuple(point) for point in definition["spawns"]}) != len(definition["spawns"]):
            raise ValueError(f"{key} : positions de spawn dupliquées.")
        for position in definition.get("spawns", []):
            if tuple(position) in blocked:
                raise ValueError(f"{key} : apparition sur un obstacle.")
        for field in ("exits", "sites", "decorations"):
            values = definition.get(field, [])
            if not isinstance(values, list) or len(values) > width * height:
                raise ValueError(f"{key} : liste {field} invalide.")
            for item in values:
                if not isinstance(item, dict):
                    raise ValueError(f"{key} : objet invalide.")
                point(item.get("position"))
                if field == "decorations" and item.get("kind") not in {"tree", "rock", "house", "flowers", "grass", "crystal", "camp", "barricade", "wall"}:
                    raise ValueError(f"{key} : décor inconnu.")
                if field == "decorations" and item.get("kind") in {"wall", "barricade"} and item["position"] not in definition["cover"]:
                    raise ValueError(f"{key} : mur ou rempart sans collision.")
                if field != "decorations" and tuple(item["position"]) in blocked:
                    raise ValueError(f"{key} : passage ou PNJ sur un obstacle.")
        if not definition.get("exits"):
            raise ValueError(f"{key} : au moins un passage est nécessaire.")
        for exit in definition["exits"]:
            minutes = exit.get("travel_minutes", 0)
            if type(minutes) not in (int, float) or not math.isfinite(minutes) or not 0 <= minutes <= 10000:
                raise ValueError(f"{key} : durée du passage invalide.")
            origin = exit.get("fast_destination")
            if origin is not None and (not isinstance(origin, str) or origin not in maps):
                raise ValueError(f"{key} : provenance du chemin rapide invalide.")
            destination = exit.get("destination")
            if destination is not None:
                if not isinstance(destination, str) or destination not in maps:
                    raise ValueError(f"{key} : destination inconnue {destination}.")
                target = maps[destination]
                if not isinstance(target, dict) or type(target.get("width")) is not int or type(target.get("height")) is not int or not isinstance(target.get("cover", []), list) or not isinstance(target.get("blocked", []), list):
                    raise ValueError(f"{key} : carte destination invalide.")
                entry = exit.get("entry")
                if not isinstance(entry, list) or len(entry) != 2 or any(type(n) is not int for n in entry) or not 0 <= entry[0] < target["width"] or not 0 <= entry[1] < target["height"] or entry in target.get("cover", []) + target.get("blocked", []):
                    raise ValueError(f"{key} : arrivée impraticable dans {destination}.")
        ids = [site.get("id") for site in definition.get("sites", [])]
        if any(not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9_:-]{1,80}", identifier) for identifier in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"{key} : identifiants PNJ invalides ou dupliqués.")
        for site in definition.get("sites", []):
            if not isinstance(site.get("id"), str) or not isinstance(site.get("name"), str) or len(site["name"]) > 100:
                raise ValueError(f"{key} : PNJ invalide.")
            if site.get("owner") is not None and not isinstance(site["owner"], str):
                raise ValueError(f"{key} : joueur lié invalide.")
            if not isinstance(site.get("dialogue", ""), str) or len(site.get("dialogue", "")) > 2000:
                raise ValueError(f"{key} : dialogue invalide.")
    dungeon_rooms = {}
    for key, definition in maps.items():
        dungeon = definition.get("dungeon")
        if not dungeon:
            continue
        room_key = (dungeon["id"], dungeon["room"])
        if room_key in dungeon_rooms:
            raise ValueError(f"{key} : salle {dungeon['room']} du donjon {dungeon['id']} dupliquée.")
        dungeon_rooms[room_key] = key
    finals = {}
    for key, definition in maps.items():
        dungeon = definition.get("dungeon")
        if dungeon and dungeon["final"]:
            if dungeon["id"] in finals:
                raise ValueError(f"{key} : plusieurs salles finales pour le donjon {dungeon['id']}.")
            finals[dungeon["id"]] = key
    from . import tactics
    from .map_building import MOBS, zone_of
    for key, definition in maps.items():
        zone_of(maps, key)
        for field in ("zone_level", "level"):
            value = definition.get(field)
            if value is not None and (type(value) is not int or not 1 <= value <= 100):
                raise ValueError(f"{key} : niveau {field} entre 1 et 100.")
        configurations = definition.get("spawners", [])
        if len(definition["spawns"]) > 64:
            raise ValueError(f"{key} : 64 spawners maximum.")
        if not isinstance(configurations, list) or len(configurations) > 64:
            raise ValueError(f"{key} : liste de spawners invalide.")
        seen = set()
        for config in configurations:
            if not isinstance(config, dict) or not isinstance(config.get("position"), list):
                raise ValueError(f"{key} : spawner invalide.")
            position = config["position"]
            if position not in definition["spawns"] or tuple(position) in seen or not isinstance(config.get("mob_id"), str) or config.get("mob_id") not in MOBS:
                raise ValueError(f"{key} : spawner dupliqué, position ou espèce invalide.")
            seen.add(tuple(position))
            if type(config.get("count", 1)) is not int or not 1 <= config.get("count", 1) <= 5:
                raise ValueError(f"{key} : groupe de 1 à 5 créatures.")
            level = config.get("level")
            if level is not None and (type(level) is not int or not 1 <= level <= 100):
                raise ValueError(f"{key} : niveau du spawner entre 1 et 100.")
            patrol = config.get("patrol", [])
            if not isinstance(patrol, list) or len(patrol) > 32:
                raise ValueError(f"{key} : patrouille de 32 points maximum.")
            previous = position
            for waypoint in patrol:
                if not tactics.walkable(definition, waypoint) or tactics.path(definition, previous, waypoint) is None:
                    raise ValueError(f"{key} : point de patrouille impraticable.")
                previous = waypoint
            if not isinstance(config.get("name", ""), str) or len(config.get("name", "")) > 100:
                raise ValueError(f"{key} : nom de spawner invalide.")
        configured_counts = {tuple(config["position"]): config.get("count", 1) for config in configurations}
        if sum(configured_counts.get(tuple(position), 1) for position in definition["spawns"]) > 128:
            raise ValueError(f"{key} : 128 créatures maximum par carte.")
        origin = definition["exits"][0]["position"]
        targets = definition.get("spawns", []) + [item["position"] for item in definition["sites"] + definition["exits"]]
        if any(tactics.path(definition, origin, target) is None for target in targets):
            raise ValueError(f"{key} : passage, PNJ ou apparition inaccessible.")
    from .map_world_editor import world_metadata
    from . import world
    world_metadata(maps, world.VILLAGE_STREETS, world.ROUTES)
    return deepcopy(maps)


def load(path):
    path = Path(path)
    if path.is_dir():
        return validate(read_catalog("fields", path))
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Fichier de cartes trop volumineux.")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def save(path, maps):
    data = validate(maps)
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def read_catalog(kind, directory=None):
    directory = Path(directory) if directory else Path(__file__).resolve().parents[1] / "maps"
    result = {}
    for path in sorted(directory.glob("*.json")):
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"Fichier trop volumineux : {path.name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("maps", data), dict):
            raise ValueError(f"Catalogue invalide : {path.name}")
        category = data.get("kind", "fields")
        definitions = data.get("maps", data)
        if category != kind:
            continue
        for key, definition in definitions.items():
            if key in result:
                raise ValueError(f"Carte dupliquée dans {path.name} : {key}")
            result[key] = definition
    if not result:
        raise ValueError(f"Aucune carte {kind} dans {directory}.")
    return result


def configured(defaults=None):
    path = os.environ.get("RPG_MAPS_FILE")
    maps = load(path) if path else validate(read_catalog("fields") if defaults is None else defaults)
    for definition in maps.values():
        geometry = {key: definition.get(key, []) for key in ("width", "height", "cover", "blocked")}
        definition["terrain_version"] = hashlib.sha256(json.dumps(geometry, sort_keys=True).encode()).hexdigest()[:16]
    return maps
