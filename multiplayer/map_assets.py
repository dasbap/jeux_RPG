import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path


def validate(maps):
    if not isinstance(maps, dict) or not maps or len(maps) > 100:
        raise ValueError("Le fichier doit contenir de 1 à 100 cartes.")
    if not {"clearing", "rosee", "lisiere", "hunt", "forest", "cave_1", "cave_2", "cave_3", "brume"} <= maps.keys():
        raise ValueError("Les cartes du tutoriel doivent être conservées.")
    maps = deepcopy(maps)
    for key, definition in maps.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", key) or not isinstance(definition, dict):
            raise ValueError("Identifiant de carte invalide.")
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
        definition.setdefault("sites", [])
        definition.setdefault("spawns", [])
        definition.setdefault("cover", [])
        definition.setdefault("blocked", [])
        blocked = {tuple(p) for p in definition.get("cover", []) + definition.get("blocked", [])}
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
                if field == "decorations" and item.get("kind") not in {"tree", "rock", "house", "flowers", "grass", "crystal", "camp"}:
                    raise ValueError(f"{key} : décor inconnu.")
                if field != "decorations" and tuple(item["position"]) in blocked:
                    raise ValueError(f"{key} : passage ou PNJ sur un obstacle.")
        if not definition.get("exits"):
            raise ValueError(f"{key} : au moins un passage est nécessaire.")
        for exit in definition["exits"]:
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
    from . import tactics
    for key, definition in maps.items():
        origin = definition["exits"][0]["position"]
        targets = definition.get("spawns", []) + [item["position"] for item in definition["sites"] + definition["exits"]]
        if any(tactics.path(definition, origin, target) is None for target in targets):
            raise ValueError(f"{key} : passage, PNJ ou apparition inaccessible.")
    return deepcopy(maps)


def load(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Fichier de cartes trop volumineux.")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def save(path, maps):
    data = validate(maps)
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def configured(defaults):
    path = os.environ.get("RPG_MAPS_FILE")
    if not path:
        return defaults
    maps = load(path)
    for definition in maps.values():
        geometry = {key: definition.get(key, []) for key in ("width", "height", "cover", "blocked")}
        definition["terrain_version"] = hashlib.sha256(json.dumps(geometry, sort_keys=True).encode()).hexdigest()[:16]
    return maps
