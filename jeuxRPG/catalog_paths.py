import os
from pathlib import Path

CATALOG_NAMES = (
    "world.json",
    "encounters.json",
    "mobs.json",
    "content.json",
    "classes.json",
)
CATALOG_LIMITS = {"content.json": 1024 * 1024, "classes.json": 2 * 1024 * 1024}
MAP_LIMIT = 8 * 1024 * 1024
PACKAGED = Path(__file__).resolve().parent / "maps"


def project_directory():
    for key in ("RPG_MAPS_FILE", "RPG_CONTENT_FILE", "RPG_CLASSES_FILE"):
        value = os.environ.get(key)
        if value:
            path = Path(value).resolve()
            return path if path.is_dir() else path.parent
    local = Path.cwd() / "maps"
    return local.resolve() if local.is_dir() else PACKAGED


def catalog_path(name, directory=None):
    if directory is not None:
        return Path(directory) / name
    override = {
        "content.json": "RPG_CONTENT_FILE",
        "classes.json": "RPG_CLASSES_FILE",
    }.get(name)
    if override and os.environ.get(override):
        return Path(os.environ[override]).resolve()
    candidate = project_directory() / name
    if candidate.exists():
        return candidate
    source = os.environ.get("RPG_MAPS_FILE")
    if source and Path(source).is_file():
        return PACKAGED / name
    return candidate


def catalog_limit(name):
    return CATALOG_LIMITS.get(name, MAP_LIMIT)
