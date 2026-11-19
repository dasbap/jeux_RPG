"""Catalog exports retain the fingerprints required by existing saved worlds."""

from pathlib import Path
from shutil import copytree

from jeuxRPG.multiplayer.controller_project import Project
from scripts.export_builder_project import catalog_identity, export_builder_project


def test_export_records_previous_world_identity_and_is_repeatable(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "projects/authored"
    shipped = tmp_path / "jeuxRPG/maps"
    copytree(root / "projects/authored", source)
    copytree(root / "jeuxRPG/maps", shipped)
    previous = catalog_identity(shipped)
    project = Project(source)
    project.maps["cave_1"]["name"] += " nouvelle version"
    project.save()
    export_builder_project(tmp_path)
    updated = Project(source)
    assert previous in updated.maps["clearing"]["previous_world_catalogs"]
    assert (source / "world.json").read_bytes() == (shipped / "world.json").read_bytes()
    first = {p.name: p.read_bytes() for p in source.glob("*.json")}
    export_builder_project(tmp_path)
    assert {p.name: p.read_bytes() for p in source.glob("*.json")} == first
