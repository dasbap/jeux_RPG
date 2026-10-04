from copy import deepcopy
from functools import lru_cache
import os
from pathlib import Path

from .map_assets import read_catalog

source = os.environ.get("RPG_MAPS_FILE")
catalog_directory = Path(source) if source and Path(source).is_dir() else Path(source).parent if source else None
MOBS = read_catalog("mobs", catalog_directory) if catalog_directory and (catalog_directory / "mobs.json").is_file() else read_catalog("mobs")


def zone_of(maps, identifier):
    seen = set()
    while True:
        if identifier in seen or identifier not in maps:
            raise ValueError("Rattachement de zone cyclique ou inexistant.")
        seen.add(identifier)
        parent = maps[identifier].get("zone_id", maps[identifier].get("world_zone", identifier))
        if not isinstance(parent, str) or parent not in maps:
            raise ValueError("Zone de rattachement invalide.")
        if parent == identifier:
            return identifier
        identifier = parent


def map_level(maps, identifier):
    explicit = maps[identifier].get("level")
    if explicit is not None:
        return explicit
    zone = zone_of(maps, identifier)
    return maps[zone].get("zone_level", 1)


def spawners(definition):
    custom = {tuple(item["position"]): item for item in definition.get("spawners", [])}
    result = []
    for position in definition.get("spawns", []):
        config = {"position": position[:], "mob_id": "goblin", "level": None, "count": 1, **deepcopy(custom.get(tuple(position), {}))}
        for _ in range(config.get("count", 1)):
            result.append(deepcopy(config))
    return result


def create_mob(maps, identifier, config, index, first=False):
    from jeuxRPG._class.character import Character
    from . import tutorial, world
    definition = MOBS[config["mob_id"]]
    actor = Character.create(definition["class_name"], "tutorial-mob", config.get("name") or f"{definition['name']} {index + 1}")
    base_hp = actor.hp.value
    level = config.get("level") or map_level(maps, identifier)
    while actor.level < level:
        actor.gain_exp(actor._required_exp_for_next_level() - actor.exp)
    if config["mob_id"] == "goblin":
        actor.hp.value = (world.GOBLIN["hp_first"] if first else world.GOBLIN["hp_hunt"]) + max(0, actor.hp.value - base_hp)
    actor.hp.current_value = actor.hp.value
    return {**tutorial.pack(actor), "mob_id": config["mob_id"], "rank": definition["rank"], "attack_damage": definition["damage"] + (level - 1) // 2,
            "loot": deepcopy(definition.get("loot", {}))}


def sync_overlap(maps, identifier):
    source = maps[identifier]
    if "world_origin" not in source:
        return 0
    count = 0
    sx, sy = source["world_origin"]
    for key, target in maps.items():
        if key == identifier or "world_origin" not in target or zone_of(maps, key) != zone_of(maps, identifier):
            continue
        tx, ty = target["world_origin"]
        common = {(x, y) for y in range(target["height"]) for x in range(target["width"]) if 0 <= x + tx - sx < source["width"] and 0 <= y + ty - sy < source["height"]}
        if not common:
            continue
        for field in ("cover", "blocked", "water", "bridges", "paths"):
            target[field] = [point for point in target.get(field, []) if tuple(point) not in common] + [[x + sx - tx, y + sy - ty] for x, y in source.get(field, []) if (x + sx - tx, y + sy - ty) in common]
        target["bridge_rotations"] = [item for item in target.get("bridge_rotations", []) if tuple(item["position"]) not in common] + [{**deepcopy(item), "position": [item["position"][0] + sx - tx, item["position"][1] + sy - ty]} for item in source.get("bridge_rotations", []) if (item["position"][0] + sx - tx, item["position"][1] + sy - ty) in common]
        target["decorations"] = [item for item in target.get("decorations", []) if tuple(item["position"]) not in common] + [{**deepcopy(item), "position": [item["position"][0] + sx - tx, item["position"][1] + sy - ty]} for item in source.get("decorations", []) if (item["position"][0] + sx - tx, item["position"][1] + sy - ty) in common]
        count += 1
    return count


@lru_cache(maxsize=32)
def species_details(identifier):
    from jeuxRPG._class.character import Character
    definition = MOBS[identifier]
    actor = Character.create(definition["class_name"], "bestiary", definition["name"])
    advantages = actor.class_table["advantage"]
    return {"hp": actor.hp.value, "stats": {key: getattr(actor, key).current_value for key in ("force", "endurance", "intelligence", "sagesse")},
            "weaknesses": [value.name for value in advantages["weakness"]], "resistances": [value.name for value in advantages["resilience"]]}


def linked_sector(maps, source_id, identifier, direction, overlap=4):
    if identifier in maps or direction not in ("est", "ouest", "nord", "sud"):
        raise ValueError("Identifiant déjà utilisé ou direction invalide.")
    source = maps[source_id]
    w, h = source["width"], source["height"]
    if not 1 <= overlap < min(w, h) - 1:
        raise ValueError("Le chevauchement doit laisser deux cases libres.")
    candidate = deepcopy(maps)
    source = candidate[source_id]
    sx, sy = source.setdefault("world_origin", [0, 0])
    dx, dy = {"est": (w-overlap, 0), "ouest": (overlap-w, 0), "sud": (0, h-overlap), "nord": (0, overlap-h)}[direction]
    target = {"id": "field_" + identifier, "name": identifier, "width": w, "height": h, "cell_metres": source.get("cell_metres", 2), "biome": source.get("biome", "forest"), "zone_id": zone_of(candidate, source_id), "world_origin": [sx+dx, sy+dy], "overlap_columns": overlap, "spawners": [], "spawns": [], "sites": [], "exits": [], "cover": [], "blocked": [], "water": [], "bridges": [], "paths": [], "decorations": []}
    candidate[identifier] = target
    sync_overlap(candidate, source_id)
    if direction in ("est", "ouest"):
        y = h//2
        forward, arrival, back, returning = ([w-1,y], [overlap,y], [0,y], [w-overlap-1,y]) if direction == "est" else ([0,y], [w-overlap-1,y], [w-1,y], [overlap,y])
    else:
        x = w//2
        forward, arrival, back, returning = ([x,h-1], [x,overlap], [x,0], [x,h-overlap-1]) if direction == "sud" else ([x,0], [x,h-overlap-1], [x,h-1], [x,overlap])
    def corridor(start, end):
        x, y = start
        points = [[x, y]]
        while x != end[0]:
            x += 1 if end[0] > x else -1
            points.append([x, y])
        while y != end[1]:
            y += 1 if end[1] > y else -1
            points.append([x, y])
        return points
    anchor = source["exits"][0]["position"]
    for data, points in ((source, corridor(forward, anchor) + corridor(returning, anchor)), (target, corridor(back, arrival))):
        for field in ("cover", "blocked", "water", "bridges"):
            data[field] = [p for p in data.get(field, []) if p not in points]
        data["bridge_rotations"] = [item for item in data.get("bridge_rotations", []) if item["position"] not in points]
        data["decorations"] = [d for d in data.get("decorations", []) if d["position"] not in points]
        for point in points:
            if point not in data["paths"]:
                data["paths"].append(point)
    source["exits"] = [g for g in source["exits"] if g["position"] != forward] + [{"position": forward, "destination": identifier, "entry": arrival, "name": "Vers " + identifier}]
    target["exits"] = [{"position": back, "destination": source_id, "entry": returning, "name": "Vers " + source["name"]}]
    from .map_assets import validate
    return validate(candidate)
