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
