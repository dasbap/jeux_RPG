"""Export the current Builder project to the catalogue shipped with the game."""

import shutil
from pathlib import Path


def export_builder_project(root):
    from jeuxRPG.catalog_paths import CATALOG_NAMES
    from jeuxRPG.multiplayer.controller_project import Project

    root = Path(root)
    source = root / "projects" / "authored"
    if not source.is_dir():
        return
    # Validate the complete project before replacing any delivered catalogue.
    Project(source).validate()
    destination = root / "jeuxRPG" / "maps"
    for name in CATALOG_NAMES:
        current, target = source / name, destination / name
        if not target.exists() or current.read_bytes() != target.read_bytes():
            shutil.copyfile(current, target)


if __name__ == "__main__":
    export_builder_project(Path(__file__).resolve().parents[1])
