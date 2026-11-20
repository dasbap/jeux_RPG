"""Export the current Builder project to the catalogue shipped with the game."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def catalog_identity(directory):
    """Read a catalogue in a fresh interpreter, independent of imported game globals."""
    environment = dict(os.environ)
    directory = Path(directory).resolve()
    environment["RPG_MAPS_FILE"] = str(directory)
    environment["RPG_CONTENT_FILE"] = str(directory / "content.json")
    environment["RPG_CLASSES_FILE"] = str(directory / "classes.json")
    code = "from jeuxRPG.multiplayer.living_world_catalog import build_catalog,fingerprint;print(fingerprint(build_catalog()))"
    return subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    ).stdout.strip()


def remember_previous_catalog(project, source, destination):
    if not all(
        (destination / name).is_file()
        for name in ("world.json", "content.json", "classes.json", "mobs.json")
    ):
        return
    if all(
        (source / name).read_bytes() == (destination / name).read_bytes()
        for name in ("world.json", "content.json", "classes.json", "mobs.json")
    ):
        return
    previous = catalog_identity(destination)
    if previous == catalog_identity(source):
        return
    history = project.maps["clearing"].setdefault("previous_world_catalogs", [])
    if previous not in history:
        history.append(previous)
        project.save()


def export_builder_project(root):
    from jeuxRPG.catalog_paths import CATALOG_NAMES
    from jeuxRPG.multiplayer.controller_project import Project

    root = Path(root)
    source = root / "projects" / "authored"
    if not source.is_dir():
        return
    # Validate the complete project before replacing any delivered catalogue.
    project = Project(source)
    project.validate()
    destination = root / "jeuxRPG" / "maps"
    destination.mkdir(parents=True, exist_ok=True)
    remember_previous_catalog(project, source, destination)
    for name in CATALOG_NAMES:
        current, target = source / name, destination / name
        if not target.exists() or current.read_bytes() != target.read_bytes():
            shutil.copyfile(current, target)


if __name__ == "__main__":
    export_builder_project(Path(__file__).resolve().parents[1])
