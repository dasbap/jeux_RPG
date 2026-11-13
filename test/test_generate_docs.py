"""Allowlisted documentation generation on small independent projects."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from __doc__.generate_docs import (
    MANIFEST_NAME,
    Documentation,
    Settings,
    extract_python_symbols,
    load_settings,
    main,
    select_files,
    write_pages,
)


def put(root, relative, text=""):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_allowlist_is_shared_by_pages_and_tree(tmp_path):
    source = put(tmp_path, "src/model.py", "class Model: pass")
    put(tmp_path, "src/readme.txt")
    put(tmp_path, ".venv/lib/private.py")
    put(tmp_path, ".signing/private.key")
    put(tmp_path, "new-tools/generated.py")
    put(tmp_path, "manual/README.md")
    settings = Settings(
        tmp_path,
        tmp_path / "generated",
        ("src/**/*.py", "src/model.py", "missing/*.py"),
    )
    files, unmatched = select_files(settings)
    assert files == [source]
    assert unmatched == ["missing/*.py"]
    pages = Documentation(settings, files).render()
    assert set(pages) == {
        "README.md",
        "TREE.md",
        "mirror/README.md",
        "mirror/src/README.md",
        "mirror/src/model.py.md",
    }
    assert "model.py" in pages["TREE.md"]
    assert all(
        name not in pages["TREE.md"]
        for name in (".venv", ".signing", "new-tools", "manual", "readme.txt")
    )
    assert "[model.py](model.py.md)" in pages["mirror/src/README.md"]
    assert "[View source](../../../src/model.py)" in pages["mirror/src/model.py.md"]


def test_config_and_overrides_are_relative_to_project(tmp_path):
    config = put(
        tmp_path,
        "__doc__/docs.toml",
        """[documentation]
output = "site"
include = ["src/**/*.py"]
[documentation.descriptions]
src = "Sources."
"src/model.py" = "Description précise."
""",
    )
    source = put(tmp_path, "src/model.py")
    settings = load_settings(tmp_path)
    assert settings.output == tmp_path / "site"
    files, _ = select_files(settings)
    assert files == [source]
    assert (
        "Description précise."
        in Documentation(settings, files).render()["mirror/src/model.py.md"]
    )
    overridden = load_settings(tmp_path, tmp_path / "other", config, ["README.md"])
    assert overridden.output == tmp_path / "other"
    assert overridden.include == ("README.md",)


@pytest.mark.parametrize(
    "pattern",
    [
        "../outside.py",
        "/tmp/*.py",
        "C:/secret/*.py",
        "C:secret.py",
        "\\\\server\\share\\*.py",
        "",
    ],
)
def test_patterns_cannot_escape_project(tmp_path, pattern):
    with pytest.raises(ValueError, match="relative"):
        Settings(tmp_path, tmp_path / "output", (pattern,))


def test_generated_output_is_never_selected(tmp_path):
    source = put(tmp_path, "src/a.py")
    put(tmp_path, "src/output/generated.py")
    settings = Settings(tmp_path, tmp_path / "src/output", ("src/**/*.py",))
    assert select_files(settings)[0] == [source]
    with pytest.raises(ValueError, match="project root"):
        Settings(tmp_path, tmp_path, ("*.py",))
    with pytest.raises(ValueError, match="project root"):
        Settings(tmp_path, tmp_path.parent, ("*.py",))


@pytest.mark.parametrize("edited", [False, True])
def test_regeneration_cleans_owned_pages_and_keeps_manual_files(tmp_path, edited):
    put(tmp_path, "a.py", "def a(): pass")
    put(tmp_path, "b.py", "def b(): pass")
    output = tmp_path / "output"
    initial = Settings(tmp_path, output, ("*.py",))
    write_pages(initial, Documentation(initial, select_files(initial)[0]).render())
    old_page = output / "mirror/a.py.md"
    if edited:
        old_page.write_text("Manual changes", encoding="utf-8")
    manual = put(output, "manual.md", "Do not delete")
    current = Settings(tmp_path, output, ("b.py",))
    preserved = write_pages(
        current, Documentation(current, select_files(current)[0]).render()
    )
    assert old_page.exists() == edited
    assert preserved == (["mirror/a.py.md"] if edited else [])
    assert manual.read_text(encoding="utf-8") == "Do not delete"
    assert "mirror/a.py.md" not in json.loads(
        (output / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert "a.py" not in (output / "TREE.md").read_text(encoding="utf-8")


def test_manifest_cannot_delete_outside_output(tmp_path):
    protected = put(tmp_path, "keep.md", "Keep me")
    put(tmp_path, "output/" + MANIFEST_NAME, json.dumps({"../keep.md": "irrelevant"}))
    settings = Settings(tmp_path, tmp_path / "output", ("*.py",))
    with pytest.raises(ValueError, match="escapes"):
        write_pages(settings, {})
    assert protected.read_text(encoding="utf-8") == "Keep me"


def test_python_encoding_async_properties_and_french_docstrings(tmp_path):
    source = tmp_path / "model.py"
    source.write_bytes(
        '''# coding: latin-1
class Model:
    """Gère les données."""
    @property
    def value(self):
        """Retourne une valeur | calculée."""
        return 1
    async def load(self):
        async def nested(): pass
'''.encode("latin-1")
    )
    classes, functions = extract_python_symbols(source)
    assert classes[0]["role"] == "Gère les données."
    assert [item["name"] for item in functions] == [
        "Model.value (property)",
        "Model.load",
        "Model.load.nested",
    ]
    assert functions[0]["line"] == "5"
    settings = Settings(tmp_path, tmp_path / "output", ("*.py",))
    page = Documentation(settings, [source]).render()["mirror/model.py.md"]
    assert "Retourne une valeur \\| calculée." in page
    assert "#L5" in page


def test_dry_run_does_not_write_and_cli_runs_from_other_directory(tmp_path):
    project = tmp_path / "project"
    put(project, "src/a.py")
    script = Path(__file__).resolve().parents[1] / "__doc__/generate_docs.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(project),
            "--include",
            "src/**/*.py",
            "--dry-run",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["src/a.py"]
    assert not (project / "__doc__").exists()
    assert main(["--root", str(project), "--include", "src/**/*.py"]) == 0
    assert (project / "__doc__/mirror/src/a.py.md").exists()


@pytest.mark.parametrize(
    "text",
    [
        '[documentation]\ninclude = "*.py"',
        "[documentation]\ninclude = []",
        '[documentation]\ninlcude = ["*.py"]',
        "[documentation]\noutput = 10",
    ],
)
def test_invalid_config_is_actionable(tmp_path, text):
    config = put(tmp_path, "docs.toml", text)
    with pytest.raises(ValueError):
        load_settings(tmp_path, config=config)


def test_file_and_directory_symlinks_are_not_selected(tmp_path):
    source = put(tmp_path, "src/a.py")
    outside = put(tmp_path.parent, tmp_path.name + "-external/outside.py")
    try:
        (tmp_path / "alias.py").symlink_to(outside)
        (tmp_path / "linked").symlink_to(outside.parent, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are not available for this Windows account")
    settings = Settings(
        tmp_path, tmp_path / "output", ("src/*.py", "alias.py", "linked/*.py")
    )
    assert select_files(settings)[0] == [source]


def test_links_encode_spaces_and_fragment_characters(tmp_path):
    source = put(tmp_path, "source files/a#b.py", "def example(): pass")
    settings = Settings(tmp_path, tmp_path / "output", ("source files/*.py",))
    page = Documentation(settings, [source]).render()["mirror/source files/a#b.py.md"]
    assert "../../../source%20files/a%23b.py" in page
    assert "a%23b.py#L1" in page


def test_links_support_output_on_another_drive(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "output", ("*.py",))
    source = put(tmp_path, "source.py")
    documentation = Documentation(settings, [source])

    def different_drives(*args):
        raise ValueError("path is on another mount")

    monkeypatch.setattr("__doc__.generate_docs.os.path.relpath", different_drives)
    assert documentation.link(Path("mirror/source.py.md"), source) == source.as_uri()
